import unittest
from unittest.mock import Mock
from tools.launch_native_virtualbox import VisibleConsole
from runtime.native_local_console import inspect_ppm
from tools.qualify_native_local_console import scancodes,KeyboardSocket,Interaction

class LocalConsoleTests(unittest.TestCase):
    @staticmethod
    def frame():
        pixels=bytearray(bytes.fromhex('E8EEEB')*320*200)
        def fill(x,y,w,h,color):
            for row in range(y,y+h):
                start=(row*320+x)*3
                pixels[start:start+w*3]=bytes.fromhex(color)*w
        fill(0,0,320,48,'F8FAF9');fill(24,16,80,2,'235B4B')
        fill(24,72,264,96,'18221E');fill(24,72,100,2,'DCE9E3')
        fill(24,86,10,2,'79C9A8')
        return b'P6\n320 200\n255\n'+pixels
    def test_local_frame_has_its_own_geometry_palette_ink_and_cursor_gate(self):
        r=inspect_ppm(self.frame())
        self.assertEqual((r['width'],r['height'],r['columns'],r['rows']),(320,200,22,6))
        self.assertTrue(r['nonblank'] and r['native_terminal_palette_observed'])
        self.assertEqual(r['terminal_pixels']['79C9A8'],20)
    def test_local_frame_rejects_blank_truncated_wrong_colors_and_lost_cursor(self):
        good=self.frame()
        for bad in [b'',good[:-1],good+b'x',good.replace(b'320 200',b'319 200'),
                    good.replace(bytes.fromhex('79C9A8'),bytes.fromhex('18221E')),
                    good.replace(bytes.fromhex('DCE9E3'),bytes.fromhex('18221E')),
                    good.replace(bytes.fromhex('F8FAF9'),bytes.fromhex('F9FAF8')),
                    b'P6\n320 200\n255\n'+b'\0'*(320*200*3)]:
            with self.assertRaises(ValueError):inspect_ppm(bad)
    def test_visible_console_only_observes_serial_and_honors_host_stop(self):
        connection=Mock()
        connection.recv.side_effect=[b'guest output',BlockingIOError()]
        console=VisibleConsole(lambda:True);console.sock=connection
        self.assertTrue(console.poll(b''))
        self.assertEqual(console.received,b'guest output')
        self.assertEqual((console.payload,console.sent),(b'',0))
        connection.send.assert_not_called()
        console.close();console.close();connection.close.assert_called_once()
    def test_visible_console_eof_and_unbounded_output_stop(self):
        for data,error in [(b'',KeyboardInterrupt),(b'x'*65537,ValueError)]:
            connection=Mock();connection.recv.return_value=data
            console=VisibleConsole(lambda:False);console.sock=connection
            with self.assertRaises(error):console.poll(b'')
            connection.send.assert_not_called();console.close()
    def test_scancodes_are_make_break_and_shift_is_balanced(self):
        self.assertEqual(scancodes(b'a'),[0x1e,0x9e])
        self.assertEqual(scancodes(b'A'),[0x2a,0x1e,0x9e,0xaa])
        self.assertEqual(scancodes(b'/'),[0x35,0xb5])
        self.assertEqual(scancodes(b'\r'),[0x1c,0x9c])
        self.assertEqual(scancodes(b'!'),[0x2a,2,0x82,0xaa])
        for byte in range(32,127):self.assertIn(len(scancodes(bytes([byte]))),(2,4))
    def test_unknown_or_bulk_input_is_not_silently_translated(self):
        for value in [b'',b'ab',b'\0',b'\xff']:
            with self.assertRaises(ValueError):scancodes(value)
    def test_keyboard_socket_cannot_write_to_serial(self):
        class Connection:
            def send(self,_):raise AssertionError('serial injection')
            def recv(self,n):return b'output'[:n]
            def close(self):pass
        seen=[];s=KeyboardSocket(Connection(),seen.append)
        self.assertEqual(s.send(b'a'),1);self.assertEqual(seen,[[0x1e,0x9e]])
        self.assertEqual(s.recv(3),b'out');s.close()
    def test_full_challenge_includes_real_apps_editing_and_shift(self):
        i=Interaction()
        try:
            self.assertIn(b'echo PooleOX\x08S!\r',i.case.sent)
            self.assertIn(b'numbers /numbers.csv\r',i.case.sent)
            self.assertTrue(i.case.sent.endswith(b'exit\r'))
            for b in i.case.sent:scancodes(bytes([b]))
        finally:i.close()

if __name__=='__main__':unittest.main()
