# Native Launch Desktop

The explicit `development-launch-desktop` kernel profile inherits
`development-launch-session`, selects `launch-console` only for trusted slot2,
and retains `launch-shell` in slot3. Ordinary window and application roles remain
separate. This is an unsigned development profile, not production admission.

No new capabilities, process factories, endpoints or executable mappings are
granted to the window service. Existing seven-page window code, five-page shell,
four-page ordinary applications, one-page guarded user stacks,36 guarded kernel
stack pages and208-page kernel limit remain. The reviewed launch-session linker
boundary is reused. The console issues typed requests; the shell owns effects.

## Qualification

Build inputs are validated separately: ordinary applications, PLCODE1 shell,
and PWCODE1 launch console. Revalidation retains every original selection,
including replaced programs; drift or missing candidates fails closed.
The console option requires the shell and complete isolated-input profile.
Serial fault injection and unreviewed feature combinations remain rejected.

The application-session qualifier builds paired kernels and optical images,
checks normal and stale-file-grant sessions, and verifies ordinary unsigned-boot
denial. This baseline alone does not prove GUI control traffic.

`tools.qualify_native_launch_desktop` consumes that exact source-bound receipt.
It removes every `start` command from the application lifecycle scenario.
Two mouse launches and two F3 launches occur while independent `echo` drafts
are pending. Shift+function-key inspection follows each launch. Actual kernel
admission identities, exact header pixels, blank fresh surface drafts, useful
file results, terminal draft output and fault/stop/restart retirement are checked.
No host serial bytes are sent; ordinary command input also uses emulated keys.
The bounded headless QEMU run retains device events, frames and transcripts.

## Remaining Boundaries

A passing GUI challenge proves only its observed guarded paths. It does not
prove every possible stack path, native failure cleanup, stale/delayed controls,
continuous typematic, arbitrary input backlog, independent COM2-free startup,
compositor recovery or persistent storage. Complete QEMU/VirtualBox input and
lifetime matrices are required before selecting a replacement preview.
The older keyboard/window/lifetime and launcher self-test validators still use
the ordinary shell profile. They must explicitly propagate and test the admitted
launch-session profile before they can qualify this image; do not weaken their
five-page/accounting checks or treat their current rejection as a passing replay.
Production graphics, accessibility, PooleGlyph/PDC and all N0-N39 gates remain.
Preserve the Cycle303 selected preview and historical evidence throughout.
