# Cycle282: Application Shell Bridge

Date:2026-10-13. Previous cycle classified as progress: owned startup handoff and
SEND-only application launch grants were host-verified and pushed. This cycle
implements the user-space shell/file-service half of the integration. Owner priority
remains the usable native ISO, followed by the complete robust microkernel.

## Implemented And Verified

PooleAppShell provides application lifecycle, file-job commands, authenticated
READY/RUN/RESULT/ACK, deliberate app faults, bounded result formatting and timeout
cleanup. PooleAppFiles explicitly opts into the two reserved app-role clients using
kernel sender identity and live reply authority. Legacy file access stays restricted.
Stop requests never fabricate retirement. Stale traffic, malformed results, restart
generations and sequence exhaustion are contained. [Contract](../native-application-shell.md).

127 user tests pass in each debug/release profile,17 new. Actual PooleText/Numbers
engines execute repeated changed-file jobs through a host IPC model.17 independent
ELF/code pairs are directly byte-identical, with no imports, writable segments or
final relocations. PooleAppShell is15136 bytes/four pages; PooleAppFiles2823/one.
13 prior programs, including both apps, match Cycle280 exactly. PooleFiles2839 bytes
and PooleFileShell9544 bytes changed and need fresh native regression runs.
Kernel source is unchanged. No native guest, useful-native-app or ISO claim follows.

Public receipt:`runs/native-app-shell-readiness.json`,27754 bytes, SHA256
`D60894BEF080CC3997C9174CF6E80EE9625648FDE1E8C9007133719DBD6FBD8C`.
It binds61 program inputs. Passing build capture11.531 seconds, log SHA256
`4E9E8B13A6F0D3A8542EA3E0BA03EF0D4366EDA24D4F1D8D7F5086CED36D1292`.
The repaired metadata/oracle suite passes285 tests in58.562 seconds,59.641 including
capture; log SHA256
`06AC0D0E4D99A11EDEDD3AAD652175D2498FC91852170B9FFEA7781E3F139E11`.
Final staged checks revalidate exact source/receipt/owner hashes, independent binary
pairs, immutable old receipts, schemas, generated roadmap and publication boundary
after closeout edits. None replace canonical qualification. Old readiness receipts
stay immutable and explicitly historical. Build directories and snapshots remain
local; no archive deletion or shared host-target cleanup is performed this cycle.

## Preserved Failures And Repair

The first host compile rejected a temporary reference in the new ACL test. A local
encoded-byte binding fixed it. The second run passed126 tests; a new composite test
incorrectly expected CRLF for an empty file. The existing file responder correctly
returns zero bytes; the test now asserts an empty, completed response.

Four freestanding candidates failed retained linker/object restrictions; the first
also exceeded four RX pages. Unsupported bounds/overflow helpers, a variable path
copy and absolute-pointer label tables were identified in the generated object.
A two-valued role enum, checked arithmetic, inline fixed result decoding, bounded
local byte copy and explicit output fields removed those dependencies. No linker,
relocation, memory-size or import acceptance rule was relaxed. All failed captures
and source snapshots remain local with their hashes in the public receipt.

The first285-test metadata pass found one assertion on next-move wording: the new
title omitted the existing exact phrase "useful applications". Restoring that
accurate qualifier repairs the title without changing acceptance. The failed
capture is retained, SHA256
`C3D900769AC49535E4F4BF88D5FD6DC95572F117B65893C4A723F4DFB2D41285`.

## Next Move And Gaps

Wire the four compiled application-profile programs into the six-role native
catalogue. Derive actual SEND-only file/control grants, preserve startup ownership
metadata and hand off the returned handles before dispatch. Admission commits
first; on handoff error retain owners and prohibit execution. Verify the launch
sequence/child-generation contract and resource/stack impact. Then native changed
input results, repeated jobs, both apps alive, stop/restart and contained app faults;
replay changed legacy files; close remaining file/cleanup controls; package and
operate the real optical ISO with sustained interaction on fresh boots.

Native integration, full stack bounds, efficient idle, general supervision and
interactive job interruption remain open. Existing32 PMM records, six roles and
16384-byte RX limit stand. Full robust microkernel, PooleGlyph/PDC and accessible
PooleGlass remain required after the usable ISO. No phase/flag closes:40 phases,
301 subphases,8996 requirements,59 additions,98 flags43 open20 gap groups.
1440 Python tests,732 architecture bindings and907 execution inputs are inventories.
No full canonical suite, main qualification, signing, release or production claim.
Owner checklist, PooleGlyph Phase65/checkpoint and conformance remain unchanged;
Phase66 is still its next step. No owner files or PooleGlyph code are changed.
