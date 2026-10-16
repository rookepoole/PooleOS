import unittest
from runtime import native_app_session as apps, native_windows as windows
from tests.test_native_app_session import file_wait_fixture


def markers(bad=False):
    result=[]
    for line in file_wait_fixture(bad):
        if 'APPS HANDOFF ' not in line:
            result.append(line);continue
        v=apps.parse(line,'HANDOFF')
        result.append(line.replace(' bytes=176 ',f' bytes={192 if v["task"]==4 else 200} '))
        v['send']=(v['generation']<<32)|0x10003
        result.append('POOLEOS:APPS SURFACE contract=PAPPSESSION1'+''.join(f' {n}={v[n]}' for n in apps.FIELDS['SURFACE'].split())+' cpl=3 production=0')
    return result


class WindowContracts(unittest.TestCase):
    def test_keyboard_bursts_preserve_every_byte_response_and_command_boundary(self):
        from tools.qualify_native_local_console import Interaction, scancodes
        i=Interaction(4);sent=[]
        try:
            i.inject=sent.append
            while i.step<len(i.case.steps):i.send_ready()
            self.assertEqual((i.sent,i.keyboard_bytes,len(i.case.sent)),(573,573,573))
            self.assertEqual(i.expected,i.case.expected)
            self.assertTrue(any(b['bytes']==4 for b in i.batches))
            self.assertEqual(len(sent),len(i.batches))
            for group,codes in zip(i.batches,sent):
                start=group['start'];count=group['bytes']
                data=i.case.sent[start:start+count]
                self.assertTrue(1<=count<=4)
                self.assertNotIn(b'\r',data[:-1])
                self.assertEqual(codes,[c for b in data for c in scancodes(bytes([b]))])
                self.assertEqual(group['scancodes'],len(codes))
        finally:i.close()

    def test_burst_send_cannot_bypass_pointer_barrier(self):
        from tools.qualify_native_windows import WindowInteraction
        i=WindowInteraction(4);sent=[]
        try:
            i.inject=sent.append;i.step=i.sustained_barrier
            before=(i.step,i.sent,i.expected)
            i.send_ready();self.assertEqual(sent,[])
            self.assertEqual((i.step,i.sent,i.expected),before)
            i.pointer_done=True;i.send_ready()
            self.assertEqual(len(sent),1);self.assertEqual(i.step,before[0]+4)
        finally:i.close()

    def test_unknown_batch_and_unbound_injector_do_not_fabricate_progress(self):
        from tools.qualify_native_local_console import Interaction
        for value in (0,2,3,8,64):
            with self.assertRaises(ValueError):Interaction(value)
        i=Interaction(4)
        try:
            with self.assertRaises(ValueError):i.send_ready()
            self.assertEqual((i.step,i.sent,i.keyboard_bytes),(0,0,0));self.assertEqual(i.batches,[])
        finally:i.close()

    def test_failed_burst_injection_is_not_counted_as_accepted_input(self):
        from tools.qualify_native_local_console import Interaction
        def fail(_):raise OSError('synthetic transport failure')
        i=Interaction(4)
        try:
            i.inject=fail
            with self.assertRaises(OSError):i.send_ready()
            self.assertEqual((i.step,i.sent,i.keyboard_bytes),(0,0,0));self.assertEqual(i.batches,[])
        finally:i.close()

    def test_mouse_injection_reaches_targets_without_large_unobserved_bursts(self):
        from tools.qualify_native_windows import bounded_motion
        for target in [(0,0),(4095,2159),(20,2000),(4000,20)]:
            x,y=2048,1080
            for _ in range(64):
                dx,dy=bounded_motion(x,y,*target)
                self.assertLessEqual(max(abs(dx),abs(dy)),96)
                x+=dx;y+=dy
                if (x,y)==target:break
            self.assertEqual((x,y),target)
        self.assertEqual(bounded_motion(1,2,1,2),(0,0))

    def test_mouse_plan_is_bounded_and_returns_pointer_to_terminal(self):
        from tools.qualify_native_windows import pointer_steps
        for w,h in [(1024,768),(1280,800),(4096,2160)]:
            steps=pointer_steps(w,h)
            self.assertEqual(len(steps),17)
            self.assertEqual(steps[-1],(40,100,False,None))
            for x,y,_,check in steps:
                self.assertTrue(0<=x<w-12 and 0<=y<h-20)
                if check:self.assertTrue(0<=check[0]<w and 0<=check[1]<h)
        for size in [(640,480),(5000,800),(1024,300)]:
            with self.assertRaises(ValueError):pointer_steps(*size)

    def test_pointer_barrier_cannot_inject_serial_or_skip_keyboard_scenario(self):
        from tools.qualify_native_windows import WindowInteraction
        class Socket:
            def close(self):pass
        i=WindowInteraction();sent=[]
        try:
            i.inject=sent.append;i.wrap(Socket());i.step=i.sustained_barrier
            self.assertEqual(i.sock.send(b'x'),0);self.assertEqual(sent,[])
            i.pointer_done=True
            self.assertEqual(i.sock.send(b'x'),1);self.assertEqual(i.keyboard_bytes,1)
            self.assertEqual(len(sent),1)
        finally:i.close()

    def test_window_handoff_requires_generation_bound_third_grant(self):
        for bad in (False,True):
            report=apps.validate_markers(markers(bad),bad_file=bad,file_waits=True,windows=True)
            self.assertEqual(len(report['surface_grants']),4)
            self.assertGreater(apps.negative_controls(markers(bad),bad_file=bad,file_waits=True,windows=True),100)

    def test_terminal_and_window_profiles_cannot_be_confused(self):
        with self.assertRaises(ValueError): apps.validate_markers(markers())
        with self.assertRaises(ValueError): apps.validate_markers(file_wait_fixture(),windows=True)
        m=markers();i=next(i for i,s in enumerate(m) if 'APPS SURFACE ' in s)
        for value in (0,0x100010001,0x200010003):
            copy=m.copy();copy[i]=copy[i].replace('send=4295032835',f'send={value}')
            with self.assertRaises(ValueError):apps.validate_markers(copy,windows=True)

    def test_pixel_oracle_requires_both_result_views_and_terminal(self):
        # Synthetic color regions exercise the oracle only, never native execution.
        w,h=1024,768;p=bytearray(bytes.fromhex('D3DFDF')*(w*h))
        def fill(x,y,width,height,color):
            for yy in range(y,y+height):
                start=(yy*w+x)*3;p[start:start+width*3]=bytes.fromhex(color)*width
        fill(0,0,w,32,'F7FAF9');fill(0,h-32,w,32,'F7FAF9')
        for x,y in [(w-320,72),(w-336,264)]:
            fill(x+1,y+28,302,147,'F8FAF9');fill(x+10,y+6,108,2,'253E37');fill(x+8,y+36,100,2,'293B35')
        fill(24,84,100,2,'DCE9E3')
        header=f'P6\n{w} {h}\n255\n'.encode()
        self.assertEqual(len(windows.inspect_ppm(header+p)['application_surfaces_observed']),2)
        fill(w-336+8,264+36,288,128,'F8FAF9')
        with self.assertRaises(ValueError):windows.inspect_ppm(header+p)

    def test_pixel_geometry_and_blank_images_reject(self):
        for data in [b'',b'P3\n640 480\n255\n',b'P6\n640 480 1\n255\n',b'P6\n640 480\n255\n'+bytes(640*480*3)]:
            with self.assertRaises(ValueError):windows.inspect_ppm(data)


if __name__=='__main__':unittest.main()
