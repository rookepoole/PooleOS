# PooleOS From-Scratch Operating System — Master Engineering Checklist

- [ ] Generated implementation checklist item count: 8,996
- [ ] Generated checklist scope: original x86-64 UEFI operating system through secure daily-driver, native drivers, PDC control plane, PooleGlyph policy layer, testing, recovery, and release engineering

- [ ] Treat this file as a living, version-controlled requirements and completion ledger.
- [ ] Require an evidence link, test receipt, or design record before checking any implementation item complete.
- [ ] Do not mark a parent subsystem complete until its implementation, tests, documentation, failure handling, and recovery items are complete.
- [ ] Re-verify every external specification revision before beginning implementation and before each public release.
- [ ] Record all deliberate omissions in a supported-features matrix rather than silently leaving behavior undefined.
- [ ] Keep the first hardware target narrow and explicitly versioned.
- [ ] Separate required, experimental, optional, deprecated, and unsupported features in the project tracker.
- [ ] Preserve raw failure evidence; do not delete failed benchmark runs, crash dumps, or negative test results.
- [ ] Never test destructive storage, firmware, voltage, clock, or power operations on the only working machine or only copy of data.
- [ ] Maintain a boot path that disables all Poole Defect Calculus actions and all experimental drivers.

## 000. Checklist Control, Definitions, and Scope

### 000.1 Document control

- [ ] Assign a document identifier.
- [ ] Assign a checklist schema version.
- [ ] Assign a PooleOS release target to the checklist.
- [ ] Record the checklist creation date.
- [ ] Record the last reviewed date.
- [ ] Record the responsible maintainer.
- [ ] Record the source repository path.
- [ ] Record the source commit hash.
- [ ] Record the generated artifact hash.
- [ ] Add a changelog section in source control.
- [ ] Require review for checklist item deletion.
- [ ] Require rationale for checklist item deferral.
- [ ] Assign stable identifiers to high-risk requirements.
- [ ] Link each milestone to the exact checklist revision used.
- [ ] Generate a machine-readable checklist export.
- [ ] Generate completion statistics by subsystem.
- [ ] Generate a list of blocked items and their blockers.
- [ ] Generate a list of experimental items enabled in each build.
- [ ] Generate a list of security-critical unchecked items.
- [ ] Generate a list of hardware-specific unchecked items.

### 000.2 Meaning of from-scratch

- [ ] Define whether the UEFI bootloader must be authored by PooleOS.
- [ ] Define whether the kernel must contain no imported kernel code.
- [ ] Define whether the C library must be authored by PooleOS.
- [ ] Define whether the shell and core utilities must be authored by PooleOS.
- [ ] Define whether the filesystem must be authored by PooleOS.
- [ ] Define whether third-party cryptographic libraries may be ported.
- [ ] Define whether third-party font rasterizers may be ported.
- [ ] Define whether third-party Unicode data may be consumed.
- [ ] Define whether vendor firmware blobs may be loaded.
- [ ] Define whether vendor microcode blobs may be loaded.
- [ ] Define whether reverse-engineered hardware knowledge may be used.
- [ ] Define whether clean-room reverse engineering is required.
- [ ] Define whether permissively licensed source may be studied but not copied.
- [ ] Define whether binary-only device firmware is acceptable.
- [ ] Define whether POSIX compatibility is a goal or only a reference.
- [ ] Define whether Linux ABI compatibility is prohibited, optional, or planned.
- [ ] Define whether Windows application compatibility is prohibited, optional, or planned.
- [ ] Define whether PooleGlyph is required for system policy at first boot.
- [ ] Define whether PDC optimization is required for the first bootable release.
- [ ] Create a signed architectural decision record for every reuse boundary.

### 000.3 Product identity

- [ ] Choose the canonical product name.
- [ ] Choose the canonical capitalization of PooleOS.
- [ ] Choose the kernel name.
- [ ] Choose the bootloader name.
- [ ] Choose the package format name.
- [ ] Choose the package manager name.
- [ ] Choose the root filesystem name if custom.
- [ ] Choose the system call ABI name.
- [ ] Choose the executable ABI name.
- [ ] Choose the service manager name.
- [ ] Choose the desktop shell name.
- [ ] Choose the recovery environment name.
- [ ] Choose the PDC control-plane service names.
- [ ] Reserve version identifiers for boot protocol, kernel ABI, user ABI, driver ABI, package format, filesystem format, and receipt format.
- [ ] Register or research conflicting trademarks before public distribution.
- [ ] Define logos, wordmarks, and usage rules separately from source licensing.

## 001. Mission, Use Cases, Non-Goals, and Completion Criteria

### 001.1 Mission definition

- [ ] Write a one-sentence operating-system mission.
- [ ] Write a technical mission statement.
- [ ] Write a user-facing mission statement.
- [ ] Define whether PooleOS is a research OS, desktop OS, gaming OS, workstation OS, server OS, appliance OS, or multiple editions.
- [ ] Define the initial user population.
- [ ] Define the initial supported hardware population.
- [ ] Define the initial threat model.
- [ ] Define the initial reliability target.
- [ ] Define the initial performance target.
- [ ] Define the initial privacy target.
- [ ] Define the initial accessibility target.
- [ ] Define the initial application-compatibility target.
- [ ] Define the initial networking target.
- [ ] Define the initial graphical target.
- [ ] Define the initial audio target.
- [ ] Define the initial storage target.
- [ ] Define the role of Poole Defect Calculus.
- [ ] Define the role of PooleGlyph.
- [ ] Define which claims require independent reproduction.
- [ ] Define what PooleOS must do better than existing systems.
- [ ] Define which advantages are hypotheses rather than established facts.

### 001.2 Initial concrete target

- [ ] Target x86-64 long mode.
- [ ] Target little-endian execution.
- [ ] Target UEFI firmware only.
- [ ] Target GPT-partitioned boot media.
- [ ] Target one explicitly inventoried desktop motherboard.
- [ ] Target one explicitly inventoried AMD Ryzen 7 9800X3D system configuration.
- [ ] Target one explicitly inventoried NVIDIA RTX 5070 board and VBIOS revision.
- [ ] Target one explicitly inventoried NVMe controller and namespace.
- [ ] Target one explicitly inventoried Ethernet controller.
- [ ] Target one explicitly inventoried Wi-Fi controller.
- [ ] Target one explicitly inventoried Bluetooth controller.
- [ ] Target one explicitly inventoried USB xHCI controller set.
- [ ] Target one explicitly inventoried audio controller and codec.
- [ ] Target one explicitly inventoried monitor and connection type.
- [ ] Target one known keyboard and one known mouse for first hardware input.
- [ ] Target one spare SSD for destructive installation tests.
- [ ] Declare all unlisted hardware unsupported until separately qualified.
- [ ] Capture firmware, BIOS, VBIOS, SSD firmware, NIC firmware, and peripheral firmware versions.
- [ ] Capture all PCI vendor IDs, device IDs, subsystem IDs, class codes, and revision IDs.
- [ ] Capture USB vendor IDs, product IDs, interface classes, and descriptor dumps.

### 001.3 Non-goals for the earliest milestones

- [ ] Do not require accelerated NVIDIA graphics for the first kernel prompt.
- [ ] Do not require Wi-Fi for the first network milestone.
- [ ] Do not require Bluetooth for the first input milestone.
- [ ] Do not require suspend-to-RAM for the first hardware boot.
- [ ] Do not require hibernation for the first production candidate.
- [ ] Do not require hot-plug CPU support for the first desktop target.
- [ ] Do not require multi-socket NUMA support for the first desktop target.
- [ ] Do not require legacy BIOS boot.
- [ ] Do not require 32-bit kernel execution.
- [ ] Do not require 16-bit user applications.
- [ ] Do not require every USB device class.
- [ ] Do not require every NVMe optional feature.
- [ ] Do not require every ACPI optional table.
- [ ] Do not require every POSIX optional interface.
- [ ] Do not require Windows driver compatibility.
- [ ] Do not require Linux kernel module compatibility.
- [ ] Do not require a custom web browser engine.
- [ ] Do not require a custom compiler backend before the kernel boots.
- [ ] Do not require machine-wide automatic PDC actuation before rollback is proven.
- [ ] Do not require permanent installation before live-media recovery is proven.

### 001.4 System-level definition of done

- [ ] Boot reliably from cold power-on on the supported machine.
- [ ] Boot reliably in the supported virtual machine configuration.
- [ ] Reach an authenticated user session without manual debugger intervention.
- [ ] Shut down without filesystem corruption.
- [ ] Reboot without firmware lockup.
- [ ] Recover automatically from a failed update.
- [ ] Boot a previous known-good system image.
- [ ] Boot a PDC-disabled safe mode.
- [ ] Detect and report unsupported hardware without undefined behavior.
- [ ] Preserve user data across normal updates.
- [ ] Verify boot and update artifacts cryptographically.
- [ ] Produce a complete hardware and software manifest.
- [ ] Produce actionable crash diagnostics.
- [ ] Pass the release security test suite.
- [ ] Pass the release storage power-loss suite.
- [ ] Pass the release long-duration stability suite.
- [ ] Pass the release performance-regression suite.
- [ ] Pass the release accessibility smoke suite.
- [ ] Pass the release installation and recovery suite.
- [ ] Publish exact limitations and unsupported features.

## 002. Requirements Engineering

### 002.1 Functional requirements

- [ ] Assign a stable identifier to every functional requirement.
- [ ] State each requirement in testable language.
- [ ] Define preconditions for each requirement.
- [ ] Define expected outputs for each requirement.
- [ ] Define error behavior for each requirement.
- [ ] Define timeout behavior for each requirement.
- [ ] Define recovery behavior for each requirement.
- [ ] Define privilege requirements for each requirement.
- [ ] Define performance budgets for latency-sensitive requirements.
- [ ] Define memory budgets for memory-sensitive requirements.
- [ ] Define storage budgets for persistent requirements.
- [ ] Define power budgets for power-sensitive requirements.
- [ ] Define observability requirements for each subsystem.
- [ ] Define compatibility requirements for each public API.
- [ ] Define deprecation rules for public interfaces.
- [ ] Trace each requirement to implementation tasks.
- [ ] Trace each requirement to one or more tests.
- [ ] Trace each requirement to documentation.
- [ ] Trace each security requirement to the threat model.
- [ ] Trace each PDC claim to a receipt schema and verifier.

### 002.2 Non-functional requirements

- [ ] Define boot-time target and measurement boundary.
- [ ] Define shutdown-time target and measurement boundary.
- [ ] Define interactive input-latency target.
- [ ] Define scheduler latency target.
- [ ] Define audio glitch-rate target.
- [ ] Define frame-pacing target.
- [ ] Define filesystem durability guarantees.
- [ ] Define update atomicity guarantees.
- [ ] Define maximum tolerable data loss after sudden power failure.
- [ ] Define maximum kernel memory overhead at idle.
- [ ] Define maximum service memory overhead at idle.
- [ ] Define maximum idle CPU utilization.
- [ ] Define maximum idle wakeup rate.
- [ ] Define maximum idle network activity.
- [ ] Define acceptable thermal behavior.
- [ ] Define minimum supported RAM capacity.
- [ ] Define minimum supported boot-device capacity.
- [ ] Define maximum tested RAM capacity.
- [ ] Define maximum tested storage size.
- [ ] Define reliability goals using explicit failure rates or test durations.
- [ ] Define accessibility conformance goals.
- [ ] Define localization goals.
- [ ] Define reproducible-build goals.
- [ ] Define supply-chain provenance goals.
- [ ] Define security-response timelines.
- [ ] Define privacy and telemetry defaults.

### 002.3 Architecture decision records

- [ ] Create an ADR for kernel architecture.
- [ ] Create an ADR for privilege-ring use.
- [ ] Create an ADR for process model.
- [ ] Create an ADR for object and handle model.
- [ ] Create an ADR for system call ABI.
- [ ] Create an ADR for executable format.
- [ ] Create an ADR for dynamic linking.
- [ ] Create an ADR for scheduler model.
- [ ] Create an ADR for virtual-memory layout.
- [ ] Create an ADR for physical-memory allocation.
- [ ] Create an ADR for driver model.
- [ ] Create an ADR for device discovery.
- [ ] Create an ADR for IOMMU policy.
- [ ] Create an ADR for VFS model.
- [ ] Create an ADR for production filesystem.
- [ ] Create an ADR for user identity and permissions.
- [ ] Create an ADR for IPC and service RPC.
- [ ] Create an ADR for package management.
- [ ] Create an ADR for atomic updates.
- [ ] Create an ADR for boot recovery.
- [ ] Create an ADR for graphics architecture.
- [ ] Create an ADR for network stack architecture.
- [ ] Create an ADR for audio architecture.
- [ ] Create an ADR for cryptographic provider architecture.
- [ ] Create an ADR for PDC privilege separation.
- [ ] Create an ADR for PooleGlyph integration.

## 003. Legal, Licensing, Policy, and Distribution

- [ ] Choose a license for the bootloader.
- [ ] Choose a license for the kernel.
- [ ] Choose a license for kernel headers.
- [ ] Choose a license for user-space libraries.
- [ ] Choose a license for user-space utilities.
- [ ] Choose a license for PooleGlyph.
- [ ] Choose a license for PDC policy files.
- [ ] Choose a license for documentation.
- [ ] Choose a license for visual assets.
- [ ] Create a third-party license policy.
- [ ] Create a source-code provenance policy.
- [ ] Create a clean-room reverse-engineering policy.
- [ ] Create a contributor certificate or contributor-license policy.
- [ ] Create a copyright-header policy.
- [ ] Create an SPDX identifier policy.
- [ ] Create a binary firmware redistribution policy.
- [ ] Verify redistribution rights for CPU microcode.
- [ ] Verify redistribution rights for GPU firmware.
- [ ] Verify redistribution rights for Wi-Fi firmware.
- [ ] Verify redistribution rights for Bluetooth firmware.
- [ ] Verify redistribution rights for NIC firmware.
- [ ] Verify redistribution rights for fonts.
- [ ] Verify redistribution rights for Unicode data.
- [ ] Verify redistribution rights for timezone data.
- [ ] Verify redistribution rights for root certificates.
- [ ] Verify redistribution rights for codec implementations.
- [ ] Track export-control considerations for cryptography.
- [ ] Track patent considerations for media codecs.
- [ ] Track patent considerations for wireless protocols.
- [ ] Track trademark usage for UEFI, USB, Bluetooth, Wi-Fi, PCIe, Vulkan, OpenGL, and vendor names.
- [ ] Create a privacy policy before collecting any telemetry.
- [ ] Create an end-user license or distribution notice if required.
- [ ] Create a vulnerability-disclosure policy.
- [ ] Create a security-contact address.
- [ ] Create a takedown and legal-request handling policy.
- [ ] Create a software-bill-of-materials publication policy.
- [ ] Create a policy for accepting proprietary documentation under NDA.
- [ ] Keep NDA-derived knowledge segregated from public clean-room code when required.
- [ ] Obtain legal review before publishing reverse-engineered proprietary driver details.

## 004. Project Governance and Repository Organization

### 004.1 Governance

- [ ] Define project owner and technical decision authority.
- [ ] Define subsystem maintainers.
- [ ] Define security maintainers.
- [ ] Define release managers.
- [ ] Define signing-key custodians.
- [ ] Define reviewer requirements for kernel changes.
- [ ] Define reviewer requirements for cryptographic changes.
- [ ] Define reviewer requirements for update-system changes.
- [ ] Define reviewer requirements for filesystem changes.
- [ ] Define reviewer requirements for PDC actuator changes.
- [ ] Define emergency security-fix authority.
- [ ] Define release-blocking severity levels.
- [ ] Define issue-priority levels.
- [ ] Define code-review expectations.
- [ ] Define design-review expectations.
- [ ] Define test-evidence requirements.
- [ ] Define benchmark-evidence requirements.
- [ ] Define deprecation process.
- [ ] Define backwards-compatibility process.
- [ ] Define incident postmortem process.

### 004.2 Repositories

- [ ] Create a bootloader repository or top-level directory.
- [ ] Create a kernel repository or top-level directory.
- [ ] Create an architecture-specific x86-64 directory.
- [ ] Create a common kernel library directory.
- [ ] Create a kernel driver directory.
- [ ] Create a firmware-interface directory.
- [ ] Create a user-space ABI headers repository.
- [ ] Create a C library repository.
- [ ] Create a runtime-support repository.
- [ ] Create a core utilities repository.
- [ ] Create a service manager repository.
- [ ] Create a package manager repository.
- [ ] Create an installer repository.
- [ ] Create a recovery environment repository.
- [ ] Create an image-builder repository.
- [ ] Create a graphical stack repository.
- [ ] Create an audio stack repository.
- [ ] Create a network-service repository.
- [ ] Create a PooleGlyph repository.
- [ ] Create a PDC control-plane repository.
- [ ] Create a benchmark and receipt repository.
- [ ] Create a conformance-tests repository.
- [ ] Create a hardware-test repository.
- [ ] Create a fuzzing repository.
- [ ] Create a documentation repository.
- [ ] Create a website and release-metadata repository.
- [ ] Create a third-party source and patches repository.
- [ ] Create a licensing and notices repository.
- [ ] Create a vulnerability advisories repository.
- [ ] Create a hardware database repository.

### 004.3 Source-tree conventions

- [ ] Define directory naming conventions.
- [ ] Define file naming conventions.
- [ ] Define public-header locations.
- [ ] Define private-header locations.
- [ ] Define generated-file locations.
- [ ] Define architecture-independent versus architecture-specific boundaries.
- [ ] Define kernel versus user-space header separation.
- [ ] Define host-tool versus target-tool separation.
- [ ] Define test-source locations.
- [ ] Define fuzz-target locations.
- [ ] Define benchmark-source locations.
- [ ] Define example-source locations.
- [ ] Define documentation-source locations.
- [ ] Define vendored-source locations.
- [ ] Define patch-series format.
- [ ] Define binary-firmware locations.
- [ ] Define generated ABI manifest locations.
- [ ] Define generated syscall table locations.
- [ ] Define generated device-ID database locations.
- [ ] Define generated Unicode and timezone database locations.

## 005. Hardware Inventory and Compatibility Database

### 005.1 Target-machine inventory

- [ ] Record motherboard manufacturer and exact model.
- [ ] Record motherboard PCB revision.
- [ ] Record firmware vendor and firmware version.
- [ ] Record AGESA version if exposed.
- [ ] Record Secure Boot state and enrolled keys.
- [ ] Record TPM vendor, firmware, and interface type.
- [ ] Record CPU model, stepping, microcode revision, and feature bits.
- [ ] Record CPU package, CCD, core, thread, cache, and NUMA topology.
- [ ] Record RAM module manufacturer, part number, capacity, ranks, and timings.
- [ ] Record memory-controller configuration.
- [ ] Record GPU manufacturer, board partner, device ID, subsystem ID, VBIOS, and connector layout.
- [ ] Record resizable-BAR configuration.
- [ ] Record NVMe manufacturer, controller, namespace, firmware, sector sizes, and capacity.
- [ ] Record Ethernet controller identifiers and PHY.
- [ ] Record Wi-Fi controller identifiers and radio capabilities.
- [ ] Record Bluetooth controller identifiers and transport.
- [ ] Record USB host controller identifiers.
- [ ] Record USB hub topology.
- [ ] Record audio controller identifiers.
- [ ] Record audio codec identifiers.
- [ ] Record Super I/O controller if discoverable.
- [ ] Record embedded controller interfaces if present.
- [ ] Record monitor manufacturer, model, EDID, DisplayID, modes, HDR, VRR, and color capabilities.
- [ ] Record keyboard and mouse descriptors.
- [ ] Record all boot-critical removable devices.
- [ ] Record PCIe topology, link widths, speeds, and ACS capabilities.
- [ ] Record IOMMU groups and interrupt-remapping capabilities.
- [ ] Record ACPI table set and checksums.
- [ ] Record SMBIOS table set and checksums.
- [ ] Record UEFI configuration-table GUIDs.
- [ ] Record power-supply and thermal-monitoring interfaces that are actually exposed to software.

### 005.2 Hardware database schema

- [ ] Store PCI vendor ID.
- [ ] Store PCI device ID.
- [ ] Store PCI subsystem vendor ID.
- [ ] Store PCI subsystem device ID.
- [ ] Store PCI revision ID.
- [ ] Store PCI class, subclass, and programming interface.
- [ ] Store USB vendor ID.
- [ ] Store USB product ID.
- [ ] Store USB device revision.
- [ ] Store USB class, subclass, and protocol.
- [ ] Store ACPI hardware IDs.
- [ ] Store ACPI compatible IDs.
- [ ] Store PNP IDs.
- [ ] Store DMI/SMBIOS match fields.
- [ ] Store firmware minimum and maximum tested versions.
- [ ] Store driver name and version.
- [ ] Store required firmware blob names and hashes.
- [ ] Store known quirks.
- [ ] Store known unsafe operations.
- [ ] Store tested power states.
- [ ] Store tested interrupt modes.
- [ ] Store tested DMA address widths.
- [ ] Store tested suspend and resume behavior.
- [ ] Store tested reset methods.
- [ ] Store support tier.
- [ ] Store evidence receipt references.
- [ ] Store last-tested date.
- [ ] Store regression status.
- [ ] Store ownership and contact metadata.

### 005.3 Hardware support tiers

- [ ] Define Tier 0 as emulator-only bootstrap support.
- [ ] Define Tier 1 as exact development-machine support.
- [ ] Define Tier 2 as same-controller-family support.
- [ ] Define Tier 3 as community-tested support.
- [ ] Define Tier 4 as best-effort unverified support.
- [ ] Define unsupported status.
- [ ] Define quarantined status for hardware with data-loss or safety defects.
- [ ] Define minimum evidence for each tier.
- [ ] Define minimum test duration for each tier.
- [ ] Define firmware-version constraints for each tier.
- [ ] Define required recovery path for each tier.
- [ ] Publish the support tier next to every driver and device entry.

## 006. Development and Hardware Laboratory

- [ ] Use a supported host operating system for development.
- [ ] Install a Linux build environment directly, in a virtual machine, or in WSL2.
- [ ] Keep a separate machine available for documentation and recovery.
- [ ] Use a dedicated spare SSD for PooleOS installation tests.
- [ ] Use at least two bootable USB devices.
- [ ] Keep one USB device immutable as known-good recovery media.
- [ ] Keep one USB device for current development images.
- [ ] Maintain verified backups of all user data.
- [ ] Maintain a full image backup of the current primary OS.
- [ ] Document motherboard firmware settings before changing them.
- [ ] Export or photograph boot-order settings.
- [ ] Export Secure Boot keys when supported and permitted.
- [ ] Keep motherboard recovery instructions offline.
- [ ] Keep firmware recovery files offline.
- [ ] Use a UPS for filesystem and update testing where appropriate.
- [ ] Use controlled power interruption only on sacrificial storage.
- [ ] Use a USB-to-serial adapter when the target board provides a serial header.
- [ ] Use a PCIe serial card only after its own driver path is understood.
- [ ] Use a second NIC or USB Ethernet adapter with a simple documented chipset for early networking.
- [ ] Use a basic USB keyboard and mouse without composite gaming features for first input.
- [ ] Use a simple 1080p monitor for first graphical output.
- [ ] Use an external power meter for energy measurements.
- [ ] Use independent temperature monitoring when testing power policy.
- [ ] Use a network tap or second machine for packet capture.
- [ ] Use a logic analyzer for low-speed buses only when electrical safety is understood.
- [ ] Use write blockers or read-only adapters when examining irreplaceable disks.
- [ ] Label every test disk physically.
- [ ] Record disk serial numbers in the test plan.
- [ ] Disable automount on the build host for destructive storage tests.
- [ ] Keep a paper or offline recovery checklist.
- [ ] Test recovery media before every destructive milestone.

## 007. Standards, Specifications, Errata, and Reference Management

- [ ] Create a local standards index with title, revision, publication date, source URL, and license.
- [ ] Download legally redistributable copies of required specifications.
- [ ] Store hashes of local specification copies.
- [ ] Track specification errata separately from base documents.
- [ ] Track vendor processor errata.
- [ ] Track motherboard firmware release notes.
- [ ] Track controller firmware release notes.
- [ ] Track device programming manuals.
- [ ] Track public register definitions.
- [ ] Track assigned-number registries.
- [ ] Track PCI vendor and device identifiers.
- [ ] Track USB class codes and usage tables.
- [ ] Track ACPI allocated identifiers.
- [ ] Track UEFI GUID registries.
- [ ] Track IANA protocol and port registries.
- [ ] Track Bluetooth assigned numbers.
- [ ] Track Unicode data-file versions.
- [ ] Track timezone database versions.
- [ ] Track root-certificate program versions.
- [ ] Track cryptographic algorithm deprecations.
- [ ] Track standards incorporated by reference.
- [ ] Record whether each document is normative, informative, draft, obsolete, or superseded.
- [ ] Record implementation assumptions derived from underspecified behavior.
- [ ] Write tests for every assumption that depends on observed hardware rather than a normative guarantee.
- [ ] Review the standards index before every subsystem design freeze.
- [ ] Review the standards index before every release.

## 008. Host Toolchain and Cross-Compilation Environment

### 008.1 Host prerequisites

- [ ] Install Git.
- [ ] Install Python 3 with a pinned version.
- [ ] Install PowerShell 7 if PowerShell orchestration is required.
- [ ] Install a C and C++ host compiler.
- [ ] Install LLVM and Clang.
- [ ] Install GNU binutils.
- [ ] Install GNU make.
- [ ] Install Ninja.
- [ ] Install CMake.
- [ ] Install Meson if selected.
- [ ] Install NASM or YASM if selected for x86 assembly.
- [ ] Install an assembler supported by the selected C compiler.
- [ ] Install Rust stable and nightly toolchains if Rust is used.
- [ ] Install QEMU system emulation.
- [ ] Install OVMF/EDK II UEFI firmware images.
- [ ] Install GDB with x86-64 target support.
- [ ] Install LLDB if selected.
- [ ] Install ELF inspection tools.
- [ ] Install PE/COFF inspection tools.
- [ ] Install disk-image tools.
- [ ] Install FAT filesystem image tools.
- [ ] Install GPT partitioning tools.
- [ ] Install compression tools.
- [ ] Install cryptographic hashing tools.
- [ ] Install code-formatting tools.
- [ ] Install static-analysis tools.
- [ ] Install documentation generators.
- [ ] Install package-signing tools.
- [ ] Install SBOM generators.
- [ ] Install container or hermetic-build tooling.
- [ ] Pin every host tool version in a lock manifest.

### 008.2 Cross compiler

- [ ] Choose the target triple.
- [ ] Choose the calling convention.
- [ ] Choose the object format.
- [ ] Choose the relocation model.
- [ ] Choose the code model.
- [ ] Choose the default CPU baseline.
- [ ] Choose optional CPU feature variants.
- [ ] Build or configure a freestanding C compiler target.
- [ ] Build or configure an assembler target.
- [ ] Build or configure a linker target.
- [ ] Build or configure an archive utility target.
- [ ] Build or configure an object-copy utility target.
- [ ] Build or configure an object-dump utility target.
- [ ] Build or configure a symbol utility target.
- [ ] Build compiler runtime builtins.
- [ ] Build integer division and remainder helpers.
- [ ] Build 128-bit arithmetic helpers if emitted.
- [ ] Build stack-protector runtime hooks.
- [ ] Build atomic runtime helpers if emitted.
- [ ] Build floating-point helper routines if emitted.
- [ ] Build unwind support only after its ABI is defined.
- [ ] Prevent accidental linkage against host headers.
- [ ] Prevent accidental linkage against host libraries.
- [ ] Create a target sysroot.
- [ ] Create kernel headers in the sysroot.
- [ ] Create user ABI headers in the sysroot.
- [ ] Create bootloader UEFI headers separately from kernel headers.
- [ ] Create debug and release target profiles.
- [ ] Create sanitizer-compatible profiles where supported.
- [ ] Create link-time-optimization profiles only after non-LTO correctness is stable.
- [ ] Create deterministic compiler flag sets.
- [ ] Record compiler version and configuration in every artifact manifest.

### 008.3 Assembly and ABI validation

- [ ] Validate register-preservation rules.
- [ ] Validate stack alignment at every C/assembly boundary.
- [ ] Validate red-zone policy.
- [ ] Validate shadow-space policy if any.
- [ ] Validate direction-flag assumptions.
- [ ] Validate floating-point control-state assumptions.
- [ ] Validate vector-register preservation rules.
- [ ] Validate interrupt-frame layout.
- [ ] Validate system-call frame layout.
- [ ] Validate context-switch frame layout.
- [ ] Validate bootloader-to-kernel handoff layout.
- [ ] Validate structure packing.
- [ ] Validate integer widths.
- [ ] Validate pointer width.
- [ ] Validate endianness.
- [ ] Validate bitfield policy or prohibit ABI-visible bitfields.
- [ ] Validate enum-size policy or prohibit ABI-visible enums without fixed widths.
- [ ] Validate name mangling for any C++ interfaces.
- [ ] Generate compile-time static assertions for ABI structures.
- [ ] Generate assembly offset files from canonical structure definitions.
- [ ] Test ABI boundaries with independent assembly fixtures.

## 009. Build System, Reproducibility, and Artifact Graph

- [ ] Choose one canonical build entrypoint.
- [ ] Support a clean build from an empty output directory.
- [ ] Separate source and build directories.
- [ ] Separate host tools from target artifacts.
- [ ] Separate bootloader, kernel, libraries, services, and image build stages.
- [ ] Declare explicit dependencies for generated files.
- [ ] Generate dependency files for C and assembly sources.
- [ ] Fail on missing generated dependencies.
- [ ] Fail on host-header leakage.
- [ ] Fail on host-library leakage.
- [ ] Fail on undeclared network access in release builds.
- [ ] Pin third-party source revisions.
- [ ] Pin binary firmware hashes.
- [ ] Pin specification-derived generated data versions.
- [ ] Normalize timestamps.
- [ ] Normalize archive member ordering.
- [ ] Normalize filesystem-image metadata.
- [ ] Normalize locale.
- [ ] Normalize timezone.
- [ ] Normalize user and group names in artifacts.
- [ ] Normalize absolute build paths in debug information.
- [ ] Set a reproducible source-date epoch.
- [ ] Record all compiler and linker flags.
- [ ] Record all environment variables that affect output.
- [ ] Generate per-component build manifests.
- [ ] Generate cryptographic hashes for every artifact.
- [ ] Generate detached signatures for release artifacts.
- [ ] Generate map files for bootloader and kernel.
- [ ] Generate symbol files for bootloader and kernel.
- [ ] Generate size reports per section and symbol.
- [ ] Generate stack-usage reports where supported.
- [ ] Generate call graphs where supported.
- [ ] Generate an SPDX SBOM.
- [ ] Generate build provenance attestations.
- [ ] Verify release reproducibility on a second clean builder.
- [ ] Compare independently rebuilt artifact hashes.
- [ ] Store reproducibility diffs when hashes do not match.

## 010. Continuous Integration and Automated Quality Gates

- [ ] Run formatting checks on every change.
- [ ] Run lint checks on every change.
- [ ] Run static analysis on every change.
- [ ] Run header self-containment checks.
- [ ] Run forbidden-host-dependency checks.
- [ ] Build debug configuration on every change.
- [ ] Build release configuration on every change.
- [ ] Build with GCC-compatible toolchain if supported.
- [ ] Build with Clang-compatible toolchain if supported.
- [ ] Build with warnings treated as errors.
- [ ] Build with maximum useful warnings.
- [ ] Build with integer-overflow diagnostics where available.
- [ ] Build with stack-usage diagnostics.
- [ ] Build with undefined-behavior sanitizer for host-testable code.
- [ ] Build with address sanitizer for host-testable code.
- [ ] Build with memory sanitizer where feasible.
- [ ] Build with thread sanitizer for host-testable concurrency code.
- [ ] Run unit tests.
- [ ] Run property tests.
- [ ] Run parser and serializer round-trip tests.
- [ ] Run ABI-layout tests.
- [ ] Run bootloader image validation.
- [ ] Run UEFI boot in QEMU.
- [ ] Run kernel boot in QEMU.
- [ ] Run serial-console smoke test.
- [ ] Run deterministic shutdown smoke test.
- [ ] Run filesystem image checks.
- [ ] Run package signature checks.
- [ ] Run update rollback simulation.
- [ ] Run fuzz-smoke corpus.
- [ ] Run source-license checks.
- [ ] Run SBOM validation.
- [ ] Run reproducibility comparison on scheduled builds.
- [ ] Run extended emulator matrix nightly.
- [ ] Run hardware-in-the-loop tests on controlled branches.
- [ ] Require all release gates before signing.
- [ ] Archive logs, serial output, crash dumps, and test receipts.

## 011. Coding Standards and Low-Level Safety Rules

- [ ] Define supported C language revision.
- [ ] Define supported C++ language revision if used.
- [ ] Define supported Rust edition if used.
- [ ] Define assembly syntax.
- [ ] Define naming conventions.
- [ ] Define error-code conventions.
- [ ] Define status-result types.
- [ ] Define ownership conventions.
- [ ] Define lifetime conventions.
- [ ] Define nullability annotations.
- [ ] Define integer-overflow policy.
- [ ] Define signed-overflow prohibition.
- [ ] Define pointer-arithmetic policy.
- [ ] Define alignment policy.
- [ ] Define packed-structure policy.
- [ ] Define volatile-use policy.
- [ ] Define atomic-use policy.
- [ ] Define memory-ordering policy.
- [ ] Define lock-order policy.
- [ ] Define interrupt-context restrictions.
- [ ] Define non-maskable-interrupt restrictions.
- [ ] Define allocation restrictions by context.
- [ ] Define blocking restrictions by context.
- [ ] Define logging restrictions by context.
- [ ] Define panic versus recoverable-error rules.
- [ ] Define assertion behavior for debug and release builds.
- [ ] Define user-pointer validation rules.
- [ ] Define MMIO access wrappers.
- [ ] Define port-I/O access wrappers.
- [ ] Define endian-conversion helpers.
- [ ] Define unaligned-access helpers.
- [ ] Define constant-time coding requirements for secrets.
- [ ] Define secret-zeroization rules.
- [ ] Define sensitive-log redaction rules.
- [ ] Define API stability annotations.
- [ ] Define deprecated API annotations.
- [ ] Define experimental API annotations.
- [ ] Define test-only code boundaries.
- [ ] Define comments required for hardware errata workarounds.
- [ ] Define comments required for security invariants.
- [ ] Define comments required for non-obvious assembly.
- [ ] Require static analysis exemptions to include rationale and owner.

## 012. Emulation, Simulation, and Debug Infrastructure

- [ ] Create a canonical QEMU machine configuration.
- [ ] Pin the QEMU version used for release tests.
- [ ] Pin the OVMF/EDK II firmware image used for release tests.
- [ ] Create a virtual disk image generator.
- [ ] Create a virtual CD/ISO image generator if needed.
- [ ] Create a virtual USB boot path.
- [ ] Create a serial console capture path.
- [ ] Create a debug console port path.
- [ ] Create a QEMU exit device or equivalent automated test completion signal.
- [ ] Create a QEMU GDB-stub launch mode.
- [ ] Create debugger scripts for loading bootloader symbols.
- [ ] Create debugger scripts for loading relocated kernel symbols.
- [ ] Create debugger scripts for switching process address spaces.
- [ ] Create pretty-printers for kernel structures.
- [ ] Create scripts for dumping page tables.
- [ ] Create scripts for dumping scheduler run queues.
- [ ] Create scripts for dumping object and handle tables.
- [ ] Create scripts for dumping PCI configuration.
- [ ] Create scripts for dumping ACPI tables.
- [ ] Create scripts for inspecting interrupt routing.
- [ ] Create deterministic virtual time tests where feasible.
- [ ] Create virtual network topologies.
- [ ] Create packet-capture integration.
- [ ] Create virtual power-loss storage tests.
- [ ] Create snapshot and rollback workflows.
- [ ] Create emulator variants with different RAM sizes.
- [ ] Create emulator variants with one and multiple CPUs.
- [ ] Create emulator variants with and without x2APIC.
- [ ] Create emulator variants with different PCI devices.
- [ ] Create emulator variants with malformed firmware tables.
- [ ] Create emulator variants with missing optional firmware services.
- [ ] Create emulator variants with read-only boot media.
- [ ] Create emulator variants with disk-full conditions.
- [ ] Create emulator variants with injected I/O errors.

## 013. On-Disk Image, Partitioning, and Boot-Media Construction

- [ ] Choose the development image container format.
- [ ] Choose the release image container format.
- [ ] Define total disk-image size.
- [ ] Create a protective MBR for GPT media.
- [ ] Create a primary GPT header.
- [ ] Create a backup GPT header.
- [ ] Create a GPT partition-entry array.
- [ ] Generate unique disk GUIDs unless reproducible test images require fixed identifiers.
- [ ] Generate unique partition GUIDs unless reproducible test images require fixed identifiers.
- [ ] Create an EFI System Partition.
- [ ] Format the EFI System Partition as FAT32.
- [ ] Choose the EFI System Partition size.
- [ ] Create a boot-artifact directory layout.
- [ ] Create a recovery partition or recovery image.
- [ ] Create active and inactive system slots if using A/B updates.
- [ ] Create a user-data partition.
- [ ] Create a crash-dump partition or reserved file.
- [ ] Create a persistent-log partition or reserved directory.
- [ ] Create a benchmark-receipt partition or reserved directory.
- [ ] Create swap space only after swap design is complete.
- [ ] Align partitions to appropriate boundaries.
- [ ] Preserve physical-sector alignment.
- [ ] Record logical and physical sector sizes.
- [ ] Validate GPT CRCs.
- [ ] Validate FAT metadata.
- [ ] Validate boot file paths.
- [ ] Validate removable-media fallback path `EFI/BOOT/BOOTX64.EFI`.
- [ ] Validate firmware-created NVRAM boot entries.
- [ ] Validate media on real firmware.
- [ ] Validate media on OVMF.
- [ ] Generate a manifest of every file and hash in the image.
- [ ] Generate a byte-for-byte image hash.
- [ ] Provide a safe image-writing command for Windows PowerShell.
- [ ] Provide a safe image-writing command for Linux.
- [ ] Require explicit target-disk confirmation in writing tools.
- [ ] Refuse to overwrite a disk containing mounted filesystems.
- [ ] Refuse to overwrite the build host system disk by default.
- [ ] Support dry-run image writing.
- [ ] Verify the written media after flashing.

## 014. Boot Protocol and Boot Information Contract

- [ ] Define the bootloader-to-kernel handoff structure.
- [ ] Version the handoff structure.
- [ ] Specify handoff structure size.
- [ ] Specify handoff structure alignment.
- [ ] Specify physical versus virtual address semantics.
- [ ] Specify ownership of every pointed-to buffer.
- [ ] Specify lifetime of every pointed-to buffer.
- [ ] Specify memory-map representation.
- [ ] Specify framebuffer representation.
- [ ] Specify ACPI RSDP representation.
- [ ] Specify SMBIOS entry-point representation.
- [ ] Specify UEFI system-table representation if retained.
- [ ] Specify UEFI runtime-services representation if retained.
- [ ] Specify initramfs representation.
- [ ] Specify kernel command-line encoding.
- [ ] Specify boot-device identity.
- [ ] Specify boot-slot identity.
- [ ] Specify boot-attempt counter state.
- [ ] Specify secure-boot state.
- [ ] Specify measured-boot state.
- [ ] Specify random seed handoff.
- [ ] Specify entropy quality flags.
- [ ] Specify firmware memory attributes.
- [ ] Specify loaded kernel image bounds.
- [ ] Specify loaded module table.
- [ ] Specify crash-kernel reservation if used.
- [ ] Specify early-log buffer.
- [ ] Specify boot timestamp data.
- [ ] Specify CPU bootstrap information.
- [ ] Specify checksum or hash for the handoff structure.
- [ ] Reject incompatible handoff versions.
- [ ] Test forward-compatible extension fields.
- [ ] Test missing optional fields.
- [ ] Test malformed lengths and addresses.

## 015. UEFI Bootloader

### 015.1 UEFI application foundation

- [ ] Create a PE32+ EFI application for x86-64.
- [ ] Use the correct EFI application subsystem.
- [ ] Use the Microsoft x64 calling convention required by UEFI.
- [ ] Provide the EFI entry point.
- [ ] Validate the EFI image with independent tooling.
- [ ] Initialize access to the EFI system table.
- [ ] Initialize access to boot services.
- [ ] Initialize access to runtime services.
- [ ] Validate table signatures.
- [ ] Validate table header sizes.
- [ ] Validate table CRCs where applicable.
- [ ] Store the firmware vendor string.
- [ ] Store the firmware revision.
- [ ] Implement UTF-16 console output.
- [ ] Implement serial output independent of the firmware console where possible.
- [ ] Implement bootloader panic output.
- [ ] Implement bootloader assertions.
- [ ] Implement bootloader status-code formatting.
- [ ] Avoid depending on firmware console output after ExitBootServices.

### 015.2 UEFI protocol discovery

- [ ] Locate the Loaded Image Protocol.
- [ ] Locate the Device Path Protocol.
- [ ] Locate the Simple File System Protocol.
- [ ] Locate the Block I/O Protocol where required.
- [ ] Locate the Disk I/O Protocol where required.
- [ ] Locate the Graphics Output Protocol.
- [ ] Locate the RNG Protocol when available.
- [ ] Locate the TCG2 Protocol when available.
- [ ] Locate the Simple Text Input Ex Protocol when required.
- [ ] Locate the Simple Network Protocol only if network boot is implemented.
- [ ] Locate the HTTP Boot protocols only if network boot is implemented.
- [ ] Locate the firmware volume protocols only if needed.
- [ ] Enumerate configuration tables.
- [ ] Locate the ACPI 2.0 or later table GUID.
- [ ] Locate the SMBIOS 3 entry-point GUID.
- [ ] Locate the SMBIOS 2 entry-point GUID as fallback.
- [ ] Locate the memory-attributes table if present.
- [ ] Locate the properties table if present.
- [ ] Handle duplicate or malformed protocol instances.
- [ ] Handle protocols absent on valid firmware.

### 015.3 Filesystem and configuration loading

- [ ] Open the loaded image's device handle.
- [ ] Open the EFI System Partition filesystem.
- [ ] Normalize EFI path separators.
- [ ] Implement exact case behavior expected by FAT/UEFI.
- [ ] Open the boot configuration file.
- [ ] Define boot configuration encoding.
- [ ] Define boot configuration grammar.
- [ ] Validate configuration lengths.
- [ ] Validate numeric ranges.
- [ ] Validate duplicate keys.
- [ ] Validate unknown keys according to policy.
- [ ] Validate path traversal.
- [ ] Load kernel image.
- [ ] Load initramfs image.
- [ ] Load optional kernel modules.
- [ ] Load optional symbol bundle for debug builds.
- [ ] Load optional microcode bundle.
- [ ] Load optional firmware bundle manifest.
- [ ] Hash every loaded artifact.
- [ ] Verify every required artifact signature.
- [ ] Reject truncated files.
- [ ] Reject oversized files.
- [ ] Reject overlapping load ranges.
- [ ] Reject incompatible architecture.
- [ ] Reject incompatible boot protocol version.
- [ ] Provide clear recovery error messages.

### 015.4 ELF kernel loading

- [ ] Validate ELF magic.
- [ ] Validate ELF class as 64-bit.
- [ ] Validate little-endian encoding.
- [ ] Validate ELF version.
- [ ] Validate machine type as x86-64.
- [ ] Validate file type.
- [ ] Validate program-header offset and count.
- [ ] Validate program-header entry size.
- [ ] Validate all file bounds before reading.
- [ ] Validate load segment sizes.
- [ ] Validate file size not greater than memory size for load segments.
- [ ] Validate load segment alignment.
- [ ] Allocate pages for load segments.
- [ ] Copy file-backed bytes.
- [ ] Zero BSS bytes.
- [ ] Apply required relocations for position-independent kernel loading.
- [ ] Reject unsupported relocation types.
- [ ] Enforce W^X-compatible segment permissions in the handoff plan.
- [ ] Record kernel physical bounds.
- [ ] Record kernel virtual bounds.
- [ ] Record kernel entry point.
- [ ] Randomize kernel placement if KASLR is enabled.
- [ ] Measure the exact loaded image if measured boot is enabled.

### 015.5 Graphics Output Protocol handoff

- [ ] Enumerate GOP handles.
- [ ] Select the intended GPU or console handle.
- [ ] Enumerate available modes.
- [ ] Validate mode information sizes.
- [ ] Select a safe initial mode.
- [ ] Prefer a supported native or known-good mode.
- [ ] Record horizontal resolution.
- [ ] Record vertical resolution.
- [ ] Record pixels per scan line.
- [ ] Record pixel format.
- [ ] Record color masks for bitmask modes.
- [ ] Record framebuffer physical base.
- [ ] Record framebuffer byte size.
- [ ] Clear the framebuffer before handoff if desired.
- [ ] Render boot diagnostics without assuming tightly packed rows.
- [ ] Avoid unsupported BLT-only modes for persistent framebuffer use.
- [ ] Preserve a text-only fallback path.
- [ ] Test monitors with different EDID mode sets.

### 015.6 UEFI memory map and ExitBootServices

- [ ] Query required memory-map buffer size.
- [ ] Allocate memory-map buffer with growth margin.
- [ ] Retrieve memory map.
- [ ] Record descriptor size.
- [ ] Record descriptor version.
- [ ] Record map key.
- [ ] Copy required firmware tables before exit if their lifetime is not guaranteed.
- [ ] Avoid allocations after final memory-map retrieval.
- [ ] Retry the complete memory-map retrieval when ExitBootServices returns an invalid key.
- [ ] Call ExitBootServices with the correct image handle and map key.
- [ ] Never call boot services after successful ExitBootServices.
- [ ] Classify every UEFI memory type.
- [ ] Preserve runtime-services regions if runtime services are retained.
- [ ] Preserve ACPI reclaim memory until tables are copied or parsed.
- [ ] Preserve ACPI NVS memory.
- [ ] Preserve memory-mapped I/O regions.
- [ ] Preserve framebuffer memory.
- [ ] Preserve bootloader, kernel, initramfs, and handoff memory.
- [ ] Release eligible boot-services code and data only after the kernel owns the map.
- [ ] Log the final memory map to the early-log buffer.
- [ ] Test firmware that changes the map during console output.
- [ ] Test firmware that returns larger descriptor sizes than the local structure definition.

### 015.7 Boot menu and recovery selection

- [ ] Implement a boot-entry data model.
- [ ] Implement default entry selection.
- [ ] Implement timeout behavior.
- [ ] Implement keyboard navigation.
- [ ] Implement serial-console navigation where possible.
- [ ] Implement normal boot entry.
- [ ] Implement PDC-disabled safe-mode entry.
- [ ] Implement previous-known-good entry.
- [ ] Implement recovery-environment entry.
- [ ] Implement diagnostic entry.
- [ ] Implement memory-test entry if available.
- [ ] Implement firmware-setup entry if supported.
- [ ] Display boot-slot health.
- [ ] Display remaining boot attempts.
- [ ] Display signature-verification status.
- [ ] Display last boot-failure reason.
- [ ] Prevent untrusted configuration from bypassing signature requirements.
- [ ] Allow a physical-presence override only under explicit policy.
- [ ] Record the selected entry in the handoff.

### 015.8 UEFI variables and boot state

- [ ] Define variable vendor GUIDs.
- [ ] Define variable names.
- [ ] Define variable attributes.
- [ ] Version variable payloads.
- [ ] Validate variable payload lengths.
- [ ] Validate variable payload checksums or signatures where needed.
- [ ] Store current system slot.
- [ ] Store pending system slot.
- [ ] Store boot attempt count.
- [ ] Store boot success state.
- [ ] Store last failure code.
- [ ] Store recovery request.
- [ ] Store safe-mode request.
- [ ] Store update transaction identifier.
- [ ] Avoid excessive NVRAM writes.
- [ ] Handle out-of-resources responses.
- [ ] Handle read-only firmware variables.
- [ ] Handle variable authentication requirements.
- [ ] Provide a file-backed fallback for non-security-critical state.
- [ ] Never store secrets in plaintext UEFI variables.
- [ ] Test variable persistence across reboot and firmware reset.

## 016. Secure Boot, Measured Boot, and Boot Integrity

- [ ] Define the trust root for release signing.
- [ ] Create an offline root signing key.
- [ ] Create an intermediate release signing key.
- [ ] Create a development signing key.
- [ ] Create a key-rotation policy.
- [ ] Create a key-revocation policy.
- [ ] Create a compromised-key incident procedure.
- [ ] Sign the UEFI bootloader.
- [ ] Verify the kernel signature in the bootloader.
- [ ] Verify initramfs signature.
- [ ] Verify module signatures.
- [ ] Verify recovery-image signature.
- [ ] Verify update-manifest signature.
- [ ] Bind signatures to artifact type and version.
- [ ] Prevent version rollback below the minimum secure version.
- [ ] Define development-mode behavior.
- [ ] Display unmistakable development-mode status.
- [ ] Integrate UEFI Secure Boot state into the handoff.
- [ ] Integrate TPM 2.0 event logging.
- [ ] Measure bootloader configuration.
- [ ] Measure kernel image.
- [ ] Measure initramfs image.
- [ ] Measure kernel modules.
- [ ] Measure system-slot metadata.
- [ ] Measure PDC policy bundle.
- [ ] Measure PooleGlyph policy bundle.
- [ ] Choose PCR allocation and event types.
- [ ] Preserve the TCG event log for user-space attestation.
- [ ] Implement local measured-boot verification.
- [ ] Plan remote attestation only after local semantics are stable.
- [ ] Test Secure Boot enabled and disabled paths.
- [ ] Test revoked signer behavior.
- [ ] Test malformed signature behavior.
- [ ] Test valid signature over wrong artifact behavior.
- [ ] Test measured-boot log replay.

## 017. Kernel Image Format, Linker Layout, and Relocation

- [ ] Choose a relocatable or fixed virtual kernel layout.
- [ ] Define kernel virtual base.
- [ ] Define physical load constraints.
- [ ] Define text section.
- [ ] Define read-only data section.
- [ ] Define initialized data section.
- [ ] Define BSS section.
- [ ] Define per-CPU template section.
- [ ] Define init-only text section.
- [ ] Define init-only data section.
- [ ] Define exception table section.
- [ ] Define unwind-information section if used.
- [ ] Define symbol table retention policy.
- [ ] Define debug-information retention policy.
- [ ] Define module metadata section.
- [ ] Define driver registration section.
- [ ] Define system-call metadata section.
- [ ] Define test-registration section.
- [ ] Define boot protocol note section.
- [ ] Align large sections to page boundaries.
- [ ] Align huge-page-eligible text when desired.
- [ ] Prevent writable and executable content sharing a page.
- [ ] Generate linker assertions for overlap.
- [ ] Generate linker assertions for canonical addresses.
- [ ] Generate linker symbols for section boundaries.
- [ ] Generate a kernel map file.
- [ ] Generate a stripped release image.
- [ ] Generate a separate debug-symbol image.
- [ ] Implement required relocation types.
- [ ] Apply relocations before enabling final page permissions.
- [ ] Reject relocation overflow.
- [ ] Randomize kernel base if KASLR is enabled.
- [ ] Record relocation slide for crash diagnostics.

## 018. Kernel Entry and Earliest Runtime

- [ ] Enter with interrupts disabled.
- [ ] Establish a known stack.
- [ ] Validate stack alignment.
- [ ] Clear direction flag.
- [ ] Disable or initialize floating-point state before use.
- [ ] Validate boot protocol magic and version.
- [ ] Validate handoff structure bounds.
- [ ] Validate handoff checksum or hash.
- [ ] Validate canonical addresses.
- [ ] Validate non-overlapping boot buffers.
- [ ] Initialize an early serial console.
- [ ] Initialize an early framebuffer console.
- [ ] Initialize an early ring-buffer logger.
- [ ] Print build identifier.
- [ ] Print kernel hash or build ID.
- [ ] Print bootloader version.
- [ ] Print firmware identity.
- [ ] Print secure-boot state.
- [ ] Print measured-boot state.
- [ ] Print command line.
- [ ] Print memory-map summary.
- [ ] Initialize a boot-time allocator.
- [ ] Reserve kernel image memory.
- [ ] Reserve bootloader handoff memory.
- [ ] Reserve initramfs memory.
- [ ] Reserve framebuffer memory.
- [ ] Reserve ACPI NVS memory.
- [ ] Reserve runtime-service memory if retained.
- [ ] Construct initial page tables if not supplied.
- [ ] Switch to the canonical kernel virtual layout.
- [ ] Install the bootstrap GDT.
- [ ] Install the bootstrap IDT.
- [ ] Install a bootstrap TSS.
- [ ] Initialize panic handling.
- [ ] Run earliest architecture self-tests.
- [ ] Transition into architecture-independent kernel initialization.

## 019. Early Logging, Console, Panic, and Crash Foundations

- [ ] Implement a lock-free or early-safe log buffer.
- [ ] Implement log severity levels.
- [ ] Implement subsystem identifiers.
- [ ] Implement timestamp fields once a clock is available.
- [ ] Implement CPU and thread identifiers once available.
- [ ] Implement source-location fields for debug builds.
- [ ] Implement serial sink.
- [ ] Implement framebuffer text sink.
- [ ] Implement in-memory sink.
- [ ] Implement user-space log export later.
- [ ] Ensure logging works before heap initialization.
- [ ] Ensure panic logging works with interrupts disabled.
- [ ] Ensure panic logging works after allocator corruption.
- [ ] Ensure panic logging avoids recursive locks.
- [ ] Implement hexadecimal integer formatting.
- [ ] Implement decimal integer formatting.
- [ ] Implement pointer formatting with security redaction policy.
- [ ] Implement bounded string formatting.
- [ ] Prohibit unbounded format operations in the kernel.
- [ ] Implement assertion failure output.
- [ ] Implement stack trace output.
- [ ] Implement register dump output.
- [ ] Implement control-register dump output.
- [ ] Implement page-fault information output.
- [ ] Implement current task output.
- [ ] Implement current address-space output.
- [ ] Implement interrupt-state output.
- [ ] Implement nested-panic detection.
- [ ] Implement double-fault emergency output.
- [ ] Implement NMI-safe emergency output where feasible.
- [ ] Implement reboot-after-panic policy.
- [ ] Implement halt-after-panic policy.
- [ ] Implement crash-dump trigger.
- [ ] Preserve last panic summary for next boot.
- [ ] Create panic-code taxonomy.
- [ ] Test panic before and after each major initialization stage.

## 020. x86-64 Processor Architecture Initialization

### 020.1 Processor identification

- [ ] Execute CPUID leaf 0 and record the maximum basic leaf.
- [ ] Record CPU vendor string.
- [ ] Execute extended CPUID leaf discovery.
- [ ] Record processor family, model, and stepping.
- [ ] Record brand string.
- [ ] Record feature flags by leaf and subleaf.
- [ ] Record physical-address width.
- [ ] Record virtual-address width.
- [ ] Record cache topology.
- [ ] Record deterministic cache parameters.
- [ ] Record core and thread topology.
- [ ] Record x2APIC topology.
- [ ] Record extended topology leaves when available.
- [ ] Record invariant TSC support.
- [ ] Record TSC-deadline support.
- [ ] Record APIC support.
- [ ] Record x2APIC support.
- [ ] Record NX support.
- [ ] Record page-size support.
- [ ] Record PCID and INVPCID support.
- [ ] Record global-page support.
- [ ] Record SMEP support.
- [ ] Record SMAP support.
- [ ] Record UMIP support.
- [ ] Record FSGSBASE support.
- [ ] Record XSAVE feature set and state sizes.
- [ ] Record RDRAND support.
- [ ] Record RDSEED support.
- [ ] Record hardware virtualization support.
- [ ] Record memory-encryption support if exposed.
- [ ] Record machine-check capabilities.
- [ ] Record performance-monitoring capabilities.
- [ ] Record thermal and power-monitoring capabilities.
- [ ] Compare CPUID results against the support matrix.
- [ ] Disable unsupported optional features cleanly.
- [ ] Reject unsupported mandatory features with a precise message.

### 020.2 Control registers and model-specific registers

- [ ] Define CR0 required and prohibited bits.
- [ ] Define CR4 required and optional bits.
- [ ] Define EFER required bits.
- [ ] Enable NX only when supported.
- [ ] Enable write protection for supervisor writes.
- [ ] Enable SMEP only after user mappings are established correctly.
- [ ] Enable SMAP only after copyin and copyout helpers are ready.
- [ ] Enable UMIP only after compatibility impact is tested.
- [ ] Enable FSGSBASE only with safe context-switch handling.
- [ ] Enable PCID only with correct TLB invalidation semantics.
- [ ] Enable global pages only with correct shootdown semantics.
- [ ] Configure PAT entries.
- [ ] Read and validate MTRR state.
- [ ] Define MTRR interaction policy.
- [ ] Configure syscall-related MSRs.
- [ ] Configure GS base and kernel GS base.
- [ ] Configure TSC_AUX for CPU identification if used.
- [ ] Configure x2APIC MSRs when x2APIC mode is selected.
- [ ] Configure machine-check MSRs.
- [ ] Configure performance-monitoring MSRs only through a controlled subsystem.
- [ ] Restrict user-space MSR access.
- [ ] Create typed wrappers for every accessed MSR.
- [ ] Document reserved-bit handling for every written register.
- [ ] Test feature enablement in isolation.

### 020.3 Floating-point and extended state

- [ ] Initialize x87 control word.
- [ ] Initialize MXCSR.
- [ ] Mask unsupported MXCSR bits.
- [ ] Enable OSFXSR.
- [ ] Enable OSXMMEXCPT.
- [ ] Enable OSXSAVE when supported and selected.
- [ ] Discover XCR0-supported state components.
- [ ] Select enabled XCR0 state components.
- [ ] Calculate per-task XSAVE area size.
- [ ] Choose XSAVE, XSAVEOPT, XSAVEC, or XSAVES policy.
- [ ] Allocate aligned extended-state buffers.
- [ ] Initialize a canonical clean FPU state.
- [ ] Implement first-use or eager FPU strategy.
- [ ] Implement context save.
- [ ] Implement context restore.
- [ ] Handle device-not-available exception if lazy strategy is used.
- [ ] Prevent kernel SIMD use unless explicitly bracketed.
- [ ] Save user vector state before kernel SIMD use.
- [ ] Clear sensitive vector state when required.
- [ ] Test x87 exceptions.
- [ ] Test SSE exceptions.
- [ ] Test AVX state context switches.
- [ ] Test migration across CPUs with identical feature sets.
- [ ] Reject heterogeneous feature combinations not supported by the ABI.

### 020.4 CPU errata and microcode

- [ ] Acquire the AMD processor revision guide for the target family.
- [ ] Map CPU family, model, and stepping to errata.
- [ ] Classify each applicable erratum.
- [ ] Implement required software workarounds.
- [ ] Add runtime assertions for workaround prerequisites.
- [ ] Record active workarounds in the hardware manifest.
- [ ] Acquire distributable CPU microcode updates.
- [ ] Verify microcode container integrity.
- [ ] Parse microcode revision metadata.
- [ ] Load microcode on the bootstrap processor at the correct stage.
- [ ] Load microcode on application processors at the correct stage.
- [ ] Verify revision after loading.
- [ ] Handle update rejection.
- [ ] Handle already-newer microcode.
- [ ] Record before-and-after revisions.
- [ ] Retest CPUID feature exposure after microcode update when required.
- [ ] Include microcode hash in boot receipts.
- [ ] Test boot without optional microcode bundle.
- [ ] Prevent downgrade to known-vulnerable microcode under secure policy.

## 021. Descriptor Tables, Privilege Levels, and CPU-Local State

### 021.1 Global Descriptor Table

- [ ] Define null descriptor.
- [ ] Define kernel code descriptor.
- [ ] Define kernel data descriptor.
- [ ] Define user code descriptor.
- [ ] Define user data descriptor.
- [ ] Define compatibility-mode descriptors only if needed.
- [ ] Define TSS descriptor per CPU.
- [ ] Allocate a GDT per CPU or define safe shared behavior.
- [ ] Load GDTR.
- [ ] Reload code segment through a far transfer.
- [ ] Reload data segment registers.
- [ ] Validate descriptor privilege levels.
- [ ] Validate long-mode descriptor flags.
- [ ] Prevent writable user mappings from becoming supervisor executable code.
- [ ] Test ring transitions.

### 021.2 Task State Segment and interrupt stacks

- [ ] Allocate one TSS per logical CPU.
- [ ] Set RSP0 for user-to-kernel transitions.
- [ ] Allocate a guard-protected kernel entry stack per CPU.
- [ ] Allocate an IST stack for double fault.
- [ ] Allocate an IST stack for NMI.
- [ ] Allocate an IST stack for machine check.
- [ ] Allocate additional IST stacks only with explicit rationale.
- [ ] Set I/O permission bitmap policy.
- [ ] Deny user port I/O by default.
- [ ] Load TR on every CPU.
- [ ] Update kernel stack pointer on context switch when required.
- [ ] Test stack overflow into guard pages.
- [ ] Test nested NMI behavior.
- [ ] Test double-fault stack independence.

### 021.3 Interrupt Descriptor Table

- [ ] Allocate an IDT with all 256 vectors.
- [ ] Define an entry for every architecturally defined exception.
- [ ] Define interrupt gates versus trap gates deliberately.
- [ ] Set descriptor privilege levels deliberately.
- [ ] Reserve user-callable breakpoint vector.
- [ ] Reserve user-callable overflow vector only if ABI requires it.
- [ ] Reserve vectors for local APIC functions.
- [ ] Reserve vectors for inter-processor interrupts.
- [ ] Reserve vectors for device interrupts.
- [ ] Reserve vectors for spurious interrupts.
- [ ] Reserve vectors for testing.
- [ ] Generate assembly stubs with uniform frames.
- [ ] Distinguish exceptions that push hardware error codes.
- [ ] Save all ABI-required registers.
- [ ] Preserve segment and GS state correctly.
- [ ] Clear direction flag on entry.
- [ ] Perform swapgs only under validated conditions.
- [ ] Restore state safely before IRETQ.
- [ ] Validate user return RIP and RSP are canonical.
- [ ] Prevent IRET faults from escalating uncontrollably.
- [ ] Load IDTR on every CPU.
- [ ] Test every installed vector with controlled injection where possible.

## 022. Exceptions and Fault Handling

- [ ] Implement divide-error handler.
- [ ] Implement debug-exception handler.
- [ ] Implement non-maskable interrupt handler.
- [ ] Implement breakpoint handler.
- [ ] Implement overflow handler.
- [ ] Implement bound-range handler.
- [ ] Implement invalid-opcode handler.
- [ ] Implement device-not-available handler.
- [ ] Implement double-fault handler.
- [ ] Implement invalid-TSS handler.
- [ ] Implement segment-not-present handler.
- [ ] Implement stack-segment fault handler.
- [ ] Implement general-protection fault handler.
- [ ] Implement page-fault handler.
- [ ] Implement x87 floating-point exception handler.
- [ ] Implement alignment-check handler.
- [ ] Implement machine-check handler.
- [ ] Implement SIMD floating-point exception handler.
- [ ] Implement virtualization-exception handler when applicable.
- [ ] Implement control-protection exception handler when applicable.
- [ ] Implement security-exception handler when applicable.
- [ ] Classify exceptions as recoverable user faults, recoverable kernel faults, or fatal kernel faults.
- [ ] Translate user exceptions into the chosen process signal or exception model.
- [ ] Terminate only the offending process when safe.
- [ ] Capture faulting instruction pointer.
- [ ] Capture stack pointer.
- [ ] Capture flags.
- [ ] Capture error code.
- [ ] Capture CR2 for page faults.
- [ ] Decode page-fault error bits.
- [ ] Decode general-protection context where possible.
- [ ] Prevent recursive page faults on fault-handler stacks.
- [ ] Maintain exception nesting counters.
- [ ] Enforce maximum exception nesting.
- [ ] Record machine-check bank information.
- [ ] Quarantine or shut down after uncorrected machine checks according to policy.
- [ ] Provide exception unit tests from user mode.
- [ ] Provide exception unit tests from kernel mode.

## 023. Interrupt Controller and Interrupt Routing

### 023.1 Legacy and local APIC setup

- [ ] Mask the legacy 8259 PIC.
- [ ] Optionally remap the PIC for diagnostic fallback.
- [ ] Discover local APIC addresses from ACPI MADT.
- [ ] Validate local APIC availability.
- [ ] Map local APIC MMIO with uncached attributes when using xAPIC.
- [ ] Select xAPIC or x2APIC mode.
- [ ] Enable the local APIC.
- [ ] Configure spurious interrupt vector.
- [ ] Configure error interrupt vector.
- [ ] Clear stale error status.
- [ ] Configure local vector table entries.
- [ ] Configure task priority register.
- [ ] Configure logical destination mode only if used.
- [ ] Implement end-of-interrupt operation.
- [ ] Implement local APIC ID discovery.
- [ ] Test local APIC timer interrupt.
- [ ] Test self-IPI.
- [ ] Test inter-processor interrupt.

### 023.2 I/O APIC and ACPI interrupt overrides

- [ ] Parse every MADT I/O APIC entry.
- [ ] Parse every interrupt-source override.
- [ ] Parse NMI source entries.
- [ ] Parse local APIC NMI entries.
- [ ] Map I/O APIC registers.
- [ ] Read I/O APIC version.
- [ ] Discover redirection-entry count.
- [ ] Create a global-system-interrupt namespace.
- [ ] Apply polarity overrides.
- [ ] Apply trigger-mode overrides.
- [ ] Allocate vectors for routed interrupts.
- [ ] Program destination APIC IDs.
- [ ] Mask entries before configuration.
- [ ] Unmask only after handler registration.
- [ ] Implement interrupt affinity changes.
- [ ] Implement shared interrupt registration if supported.
- [ ] Implement level-triggered EOI ordering.
- [ ] Detect stuck level-triggered interrupts.
- [ ] Rate-limit interrupt storms.
- [ ] Provide routing-table diagnostics.

### 023.3 MSI and MSI-X

- [ ] Parse PCI MSI capability.
- [ ] Parse PCI MSI-X capability.
- [ ] Determine supported message count.
- [ ] Allocate contiguous vectors when required.
- [ ] Construct MSI address and data.
- [ ] Support 32-bit and 64-bit MSI address formats.
- [ ] Mask MSI during configuration.
- [ ] Program per-vector masking if available.
- [ ] Map MSI-X table safely.
- [ ] Map MSI-X pending-bit array safely.
- [ ] Validate table BAR and offset bounds.
- [ ] Program MSI-X entries atomically while masked.
- [ ] Enable MSI or MSI-X only after handler installation.
- [ ] Disable legacy line interrupt when required.
- [ ] Support affinity updates.
- [ ] Support device reset and reprogramming.
- [ ] Release vectors on driver removal.
- [ ] Prevent untrusted user code from programming MSI destinations.
- [ ] Test malformed PCI capability chains.

### 023.4 Interrupt subsystem services

- [ ] Create interrupt-vector allocator.
- [ ] Create interrupt-handler registration API.
- [ ] Create interrupt-handler removal API.
- [ ] Create top-half and deferred-work split.
- [ ] Create per-vector statistics.
- [ ] Create per-device statistics.
- [ ] Create latency measurements.
- [ ] Create nesting accounting.
- [ ] Create interrupt-affinity API.
- [ ] Create interrupt-threading option.
- [ ] Create shared-interrupt dispatch policy.
- [ ] Create spurious-interrupt detection.
- [ ] Create unhandled-interrupt quarantine.
- [ ] Create interrupt storm suppression.
- [ ] Create handler timeout diagnostics.
- [ ] Prohibit blocking in hard interrupt context.
- [ ] Prohibit unsafe allocation in hard interrupt context.
- [ ] Test handler registration races.
- [ ] Test device removal with in-flight interrupts.

## 024. Timekeeping, Timers, and Clock Discipline

### 024.1 Clock sources

- [ ] Discover invariant TSC support.
- [ ] Calibrate TSC frequency using a trustworthy reference.
- [ ] Read CPUID frequency information when available.
- [ ] Read firmware-provided frequency information only as advisory.
- [ ] Discover HPET from ACPI when present.
- [ ] Discover ACPI PM timer when present.
- [ ] Access CMOS RTC safely.
- [ ] Select a primary monotonic clock source.
- [ ] Rank fallback clock sources.
- [ ] Detect clock source instability.
- [ ] Detect TSC synchronization problems across CPUs.
- [ ] Synchronize or compensate per-CPU clock offsets.
- [ ] Use serialization appropriate to timestamp reads.
- [ ] Convert cycles to nanoseconds without overflow.
- [ ] Maintain precision over long uptime.
- [ ] Handle counter wraparound.
- [ ] Expose clock-source diagnostics.
- [ ] Switch away from a failing clock source.

### 024.2 Clock events and timer queues

- [ ] Initialize local APIC timer.
- [ ] Support one-shot local APIC timer mode.
- [ ] Support TSC-deadline mode when reliable.
- [ ] Calibrate local APIC timer when needed.
- [ ] Create per-CPU timer queues.
- [ ] Choose timer data structure.
- [ ] Support high-resolution timers.
- [ ] Support periodic timers.
- [ ] Support absolute deadlines.
- [ ] Support relative deadlines.
- [ ] Support timer cancellation.
- [ ] Handle cancellation racing with expiration.
- [ ] Handle timer migration during CPU offline.
- [ ] Implement soft-timer deferred execution.
- [ ] Prevent timer callback starvation.
- [ ] Account timer callback runtime.
- [ ] Detect timer overruns.
- [ ] Implement scheduler tick.
- [ ] Implement tickless idle when stable.
- [ ] Implement dynamic tick for non-idle workloads only after testing.
- [ ] Test simultaneous timer expirations.
- [ ] Test very short and very long deadlines.
- [ ] Test time conversion overflow boundaries.

### 024.3 System clocks

- [ ] Define monotonic clock.
- [ ] Define boottime clock including suspend.
- [ ] Define realtime wall clock.
- [ ] Define raw hardware clock.
- [ ] Define process CPU clock.
- [ ] Define thread CPU clock.
- [ ] Define coarse clock variants if needed.
- [ ] Initialize wall clock from RTC.
- [ ] Store RTC timezone policy as UTC.
- [ ] Implement calendar conversion.
- [ ] Implement leap-year handling.
- [ ] Implement leap-second policy.
- [ ] Implement timezone handling in user space.
- [ ] Implement adjtime-style gradual correction.
- [ ] Implement clock-set privilege checks.
- [ ] Prevent realtime changes from breaking monotonic timers.
- [ ] Persist corrected wall clock on clean shutdown if policy permits.
- [ ] Handle RTC invalid or battery failure.
- [ ] Record clock synchronization status.

## 025. Symmetric Multiprocessing and CPU Lifecycle

### 025.1 CPU discovery and topology

- [ ] Parse MADT processor entries.
- [ ] Ignore disabled processors unless hot-add policy supports them.
- [ ] Map firmware processor IDs to APIC IDs.
- [ ] Cross-check CPUID topology.
- [ ] Parse ACPI PPTT when available.
- [ ] Build package topology.
- [ ] Build CCD or die topology when discoverable.
- [ ] Build core topology.
- [ ] Build simultaneous-multithreading topology.
- [ ] Build cache-sharing topology.
- [ ] Build NUMA-node topology.
- [ ] Record preferred-core information only if documented.
- [ ] Record asymmetric or heterogeneous properties if present.
- [ ] Reject unsupported topology inconsistencies safely.
- [ ] Expose topology to scheduler and user space.

### 025.2 Application processor startup

- [ ] Allocate a low-memory AP trampoline.
- [ ] Ensure trampoline physical address meets SIPI requirements.
- [ ] Provide temporary page tables accessible by APs.
- [ ] Provide per-AP startup data.
- [ ] Send INIT IPI.
- [ ] Observe required delays.
- [ ] Send first SIPI.
- [ ] Send second SIPI when required.
- [ ] Enter protected mode in trampoline.
- [ ] Enter long mode in trampoline.
- [ ] Load per-CPU GDT.
- [ ] Load per-CPU IDT.
- [ ] Load per-CPU TSS.
- [ ] Initialize per-CPU GS base.
- [ ] Initialize local APIC.
- [ ] Initialize FPU and XSAVE state.
- [ ] Load microcode if required.
- [ ] Join the online CPU set atomically.
- [ ] Signal bootstrap processor on success.
- [ ] Timeout and report failed AP startup.
- [ ] Continue with reduced CPU count when policy permits.
- [ ] Free or protect trampoline memory after startup.
- [ ] Test one-CPU and all-CPU configurations.

### 025.3 Inter-processor communication

- [ ] Implement fixed-delivery IPIs.
- [ ] Implement NMI IPIs only for controlled diagnostics.
- [ ] Implement reschedule IPI.
- [ ] Implement TLB shootdown IPI.
- [ ] Implement call-function IPI.
- [ ] Implement stop-CPU IPI.
- [ ] Implement panic freeze IPI.
- [ ] Implement time-synchronization IPI if needed.
- [ ] Define IPI vector priorities.
- [ ] Define acknowledgement mechanisms.
- [ ] Define timeout behavior.
- [ ] Avoid deadlocks while interrupts are disabled.
- [ ] Handle target CPU going offline.
- [ ] Collect IPI latency statistics.
- [ ] Stress-test concurrent IPIs.

### 025.4 CPU idle and hotplug

- [ ] Implement a safe HLT-based idle loop.
- [ ] Enable interrupts before HLT atomically.
- [ ] Integrate idle state with scheduler accounting.
- [ ] Parse ACPI idle-state information if used.
- [ ] Support deeper C-states only after latency and wake testing.
- [ ] Handle monitor/mwait only if safely supported.
- [ ] Implement CPU offline protocol if required.
- [ ] Migrate runnable tasks before offline.
- [ ] Migrate timers before offline.
- [ ] Migrate interrupts before offline.
- [ ] Drain per-CPU work queues.
- [ ] Flush per-CPU caches and allocators as required.
- [ ] Stop target CPU safely.
- [ ] Implement CPU online protocol if hotplug is supported.
- [ ] Exclude CPU hotplug from early release if not fully tested.

## 026. Physical Memory Management

### 026.1 Memory map normalization

- [ ] Parse every UEFI memory descriptor using firmware-provided descriptor size.
- [ ] Validate descriptor arithmetic for overflow.
- [ ] Sort descriptors by physical address.
- [ ] Merge compatible adjacent regions.
- [ ] Detect overlapping descriptors.
- [ ] Resolve overlaps conservatively.
- [ ] Classify usable conventional memory.
- [ ] Classify boot-services memory.
- [ ] Classify runtime-services memory.
- [ ] Classify loader memory.
- [ ] Classify ACPI reclaim memory.
- [ ] Classify ACPI NVS memory.
- [ ] Classify persistent memory.
- [ ] Classify memory-mapped I/O.
- [ ] Classify unusable memory.
- [ ] Reserve page zero.
- [ ] Reserve legacy low-memory regions.
- [ ] Reserve AP trampoline.
- [ ] Reserve firmware runtime regions.
- [ ] Reserve kernel and modules.
- [ ] Reserve initramfs.
- [ ] Reserve framebuffer.
- [ ] Reserve crash-dump region.
- [ ] Reserve DMA bounce pools.
- [ ] Reserve hardware-specific stolen memory if known.
- [ ] Expose a normalized map for diagnostics.

### 026.2 Bootstrap allocator

- [ ] Implement allocation before the main physical allocator.
- [ ] Guarantee requested alignment.
- [ ] Detect exhaustion.
- [ ] Record every allocation.
- [ ] Prevent overlap with reserved regions.
- [ ] Support zeroed allocation.
- [ ] Support permanent versus reclaimable boot allocations.
- [ ] Transfer allocation records to the main allocator.
- [ ] Reclaim eligible bootstrap memory only after all references are gone.
- [ ] Poison reclaimed memory in debug builds.

### 026.3 Main physical-page allocator

- [ ] Choose bitmap, buddy, extent, or hybrid allocator.
- [ ] Define base page size.
- [ ] Define supported large page sizes.
- [ ] Define page-frame metadata.
- [ ] Place page metadata without recursively exhausting memory.
- [ ] Create low-memory zone if needed.
- [ ] Create DMA-below-4-GiB zone.
- [ ] Create normal memory zone.
- [ ] Create per-NUMA-node zones.
- [ ] Reserve unaddressable physical ranges.
- [ ] Support single-page allocation.
- [ ] Support contiguous multi-page allocation.
- [ ] Support aligned allocation.
- [ ] Support zeroed allocation.
- [ ] Support nonblocking allocation.
- [ ] Support allocation constraints.
- [ ] Support freeing.
- [ ] Detect double free.
- [ ] Detect freeing reserved pages.
- [ ] Detect invalid page-frame numbers.
- [ ] Maintain free-page counts.
- [ ] Maintain allocation statistics.
- [ ] Maintain fragmentation statistics.
- [ ] Implement per-CPU page caches only after correctness.
- [ ] Drain per-CPU caches under pressure.
- [ ] Implement memory poisoning in debug builds.
- [ ] Implement page-owner tracking in debug builds.
- [ ] Implement allocation-failure injection.
- [ ] Test allocator invariants continuously in debug builds.

### 026.4 NUMA and topology-aware memory

- [ ] Parse ACPI SRAT.
- [ ] Parse ACPI SLIT.
- [ ] Map memory ranges to proximity domains.
- [ ] Map CPUs to proximity domains.
- [ ] Validate domain consistency.
- [ ] Define local allocation policy.
- [ ] Define interleave policy.
- [ ] Define preferred-node policy.
- [ ] Define fallback-node policy.
- [ ] Expose NUMA topology to scheduler.
- [ ] Expose NUMA topology to user space.
- [ ] Collect remote-access statistics if available.
- [ ] Defer NUMA optimization until single-node correctness is complete.

## 027. Virtual Memory and Address Spaces

### 027.1 Kernel virtual-address layout

- [ ] Define user-space range.
- [ ] Define noncanonical guard gap.
- [ ] Define kernel text range.
- [ ] Define kernel data range.
- [ ] Define direct physical map.
- [ ] Define vmalloc or dynamic-kernel-map range.
- [ ] Define per-CPU range.
- [ ] Define module range.
- [ ] Define kernel stacks range.
- [ ] Define device MMIO range.
- [ ] Define framebuffer mapping range.
- [ ] Define temporary mapping range.
- [ ] Define recursive page-table mapping only if selected.
- [ ] Define fixmap range only if selected.
- [ ] Define address-space randomization ranges.
- [ ] Document canonical-address assumptions.
- [ ] Add compile-time overlap assertions.
- [ ] Add boot-time overlap assertions.

### 027.2 Page-table management

- [ ] Support four-level paging.
- [ ] Detect and optionally support five-level paging.
- [ ] Define page-table entry helpers.
- [ ] Define present bit handling.
- [ ] Define writable bit handling.
- [ ] Define user bit handling.
- [ ] Define accessed bit handling.
- [ ] Define dirty bit handling.
- [ ] Define global bit handling.
- [ ] Define NX bit handling.
- [ ] Define cache attribute handling.
- [ ] Define software-owned bits.
- [ ] Allocate page-table pages.
- [ ] Zero new page-table pages.
- [ ] Map 4-KiB pages.
- [ ] Map 2-MiB pages.
- [ ] Map 1-GiB pages only when supported and justified.
- [ ] Unmap pages.
- [ ] Change permissions.
- [ ] Split large mappings.
- [ ] Coalesce mappings only when safe.
- [ ] Walk page tables.
- [ ] Validate canonical virtual addresses.
- [ ] Validate physical-address width.
- [ ] Reject reserved-bit combinations.
- [ ] Prevent integer overflow in ranges.
- [ ] Handle partial failures with rollback.
- [ ] Maintain reference counts for shared page tables if used.
- [ ] Free empty page-table levels.
- [ ] Dump page tables for debugging.

### 027.3 TLB and address-space identifiers

- [ ] Implement local TLB invalidation.
- [ ] Implement range invalidation.
- [ ] Implement full address-space invalidation.
- [ ] Implement global mapping invalidation.
- [ ] Implement cross-CPU TLB shootdown.
- [ ] Track CPUs using each address space.
- [ ] Batch shootdowns when safe.
- [ ] Handle CPU entry and exit races.
- [ ] Enable PCID only after semantics are correct.
- [ ] Allocate PCIDs.
- [ ] Handle PCID rollover.
- [ ] Use INVPCID where supported.
- [ ] Measure shootdown latency.
- [ ] Stress-test concurrent map and unmap operations.

### 027.4 User address spaces

- [ ] Create an empty user address space.
- [ ] Map executable segments.
- [ ] Map user stack.
- [ ] Create stack guard page.
- [ ] Randomize stack location.
- [ ] Map thread-local storage.
- [ ] Map shared libraries.
- [ ] Map shared memory.
- [ ] Map memory-mapped files.
- [ ] Support anonymous mappings.
- [ ] Support private mappings.
- [ ] Support shared mappings.
- [ ] Support fixed mappings with strict validation.
- [ ] Support protection changes.
- [ ] Support unmapping.
- [ ] Support address-space cloning.
- [ ] Support copy-on-write.
- [ ] Support demand-zero pages.
- [ ] Support demand paging from files.
- [ ] Track virtual memory areas.
- [ ] Choose a data structure for virtual memory areas.
- [ ] Handle overlapping map requests.
- [ ] Handle mapping gaps.
- [ ] Enforce per-process address-space limits.
- [ ] Destroy address spaces without leaks.
- [ ] Prevent kernel mappings from becoming user-accessible.

### 027.5 Page-fault resolution

- [ ] Distinguish present and non-present faults.
- [ ] Distinguish read, write, and execute faults.
- [ ] Distinguish user and supervisor faults.
- [ ] Distinguish reserved-bit faults.
- [ ] Distinguish protection-key faults if supported.
- [ ] Resolve demand-zero faults.
- [ ] Resolve copy-on-write faults.
- [ ] Resolve file-backed faults.
- [ ] Resolve stack-growth faults within strict limits.
- [ ] Reject null-page access.
- [ ] Reject guard-page access.
- [ ] Reject execute-on-NX access.
- [ ] Reject user access to supervisor mappings.
- [ ] Handle out-of-memory during fault resolution.
- [ ] Handle I/O failure during file-backed fault.
- [ ] Avoid holding locks across blocking I/O incorrectly.
- [ ] Terminate user process on invalid fault.
- [ ] Panic or recover according to kernel fault-table policy.
- [ ] Implement safe copyin/copyout recovery fixups.
- [ ] Record fault statistics.
- [ ] Fuzz virtual-memory operations.

## 028. Kernel Memory Allocation

### 028.1 General heap

- [ ] Define allocation API.
- [ ] Define zeroed allocation API.
- [ ] Define aligned allocation API.
- [ ] Define array allocation with overflow checking.
- [ ] Define reallocation API if allowed.
- [ ] Define free API.
- [ ] Define context flags for blocking versus nonblocking allocation.
- [ ] Define memory-accounting tags.
- [ ] Choose allocator design.
- [ ] Handle small allocations efficiently.
- [ ] Handle large allocations safely.
- [ ] Return properly aligned memory.
- [ ] Detect size overflow.
- [ ] Detect double free.
- [ ] Detect invalid free.
- [ ] Detect buffer overrun with red zones in debug builds.
- [ ] Detect use-after-free with quarantine in debug builds.
- [ ] Poison allocated and freed memory in debug builds.
- [ ] Track allocation call sites.
- [ ] Track per-subsystem usage.
- [ ] Expose leak reports.
- [ ] Implement allocation-failure injection.
- [ ] Test allocator under interrupt and SMP stress.

### 028.2 Object caches

- [ ] Create fixed-size object cache abstraction.
- [ ] Align objects for cache and hardware requirements.
- [ ] Support constructor and destructor hooks.
- [ ] Maintain partial, full, and empty slabs.
- [ ] Support per-CPU magazines only after base correctness.
- [ ] Reclaim empty slabs under pressure.
- [ ] Track object states in debug builds.
- [ ] Detect cross-cache free.
- [ ] Support cache destruction after all objects are released.
- [ ] Expose fragmentation and utilization metrics.

### 028.3 Kernel stacks

- [ ] Choose kernel stack size.
- [ ] Allocate per-thread kernel stack.
- [ ] Add lower guard page.
- [ ] Add upper guard page where practical.
- [ ] Use dedicated entry stacks if required by security design.
- [ ] Track maximum stack usage.
- [ ] Fill unused stack with canary pattern in debug builds.
- [ ] Detect stack overflow early.
- [ ] Avoid large automatic objects.
- [ ] Provide compiler stack-usage reports.
- [ ] Free stacks only after no CPU can reference them.

## 029. Cacheability, Memory Types, and MMIO

- [ ] Define normal write-back memory mappings.
- [ ] Define uncached mappings.
- [ ] Define write-combining mappings.
- [ ] Define write-through mappings only when needed.
- [ ] Program or consume PAT consistently.
- [ ] Respect firmware MTRR configuration.
- [ ] Prevent conflicting memory types for the same physical page.
- [ ] Map device registers with correct cache attributes.
- [ ] Map framebuffer with write-combining when safe.
- [ ] Define MMIO read8, read16, read32, and read64 helpers.
- [ ] Define MMIO write8, write16, write32, and write64 helpers.
- [ ] Define posted-write flush behavior.
- [ ] Define compiler barriers around MMIO.
- [ ] Define CPU memory barriers around device interaction.
- [ ] Define port-I/O helpers.
- [ ] Validate register alignment.
- [ ] Validate register width.
- [ ] Prevent speculative access where required.
- [ ] Audit every device mapping for bounds.
- [ ] Unmap device mappings on removal.

## 030. DMA and IOMMU

### 030.1 Generic DMA API

- [ ] Define coherent DMA allocation API.
- [ ] Define streaming DMA mapping API.
- [ ] Define DMA unmapping API.
- [ ] Define DMA synchronization API.
- [ ] Represent device DMA address width.
- [ ] Represent device segment-size limits.
- [ ] Represent boundary constraints.
- [ ] Represent alignment constraints.
- [ ] Represent scatter-gather lists.
- [ ] Coalesce contiguous segments when allowed.
- [ ] Split segments exceeding device limits.
- [ ] Allocate bounce buffers for inaccessible memory.
- [ ] Copy into and out of bounce buffers at correct times.
- [ ] Prevent DMA to freed memory.
- [ ] Prevent CPU access races with noncoherent DMA.
- [ ] Track outstanding mappings.
- [ ] Clean up mappings on driver removal.
- [ ] Inject DMA mapping failures for tests.

### 030.2 AMD IOMMU and generic IOMMU framework

- [ ] Parse ACPI IVRS for AMD IOMMU systems.
- [ ] Parse ACPI DMAR if future Intel support is added.
- [ ] Discover IOMMU units.
- [ ] Discover device scopes and aliases.
- [ ] Map PCI requestor IDs.
- [ ] Create translation domains.
- [ ] Create identity domain only for explicit bootstrap needs.
- [ ] Create isolated domain per device or trust group.
- [ ] Allocate I/O page tables.
- [ ] Map DMA pages.
- [ ] Unmap DMA pages.
- [ ] Invalidate IOMMU translation caches.
- [ ] Enable interrupt remapping when supported.
- [ ] Handle IOMMU faults.
- [ ] Log faulting device and address.
- [ ] Quarantine a device causing repeated faults.
- [ ] Preserve firmware-reserved mappings when required.
- [ ] Integrate IOMMU groups with device assignment.
- [ ] Disable bus mastering before domain attachment.
- [ ] Enable bus mastering only after safe mappings exist.
- [ ] Test devices with 32-bit and 64-bit DMA.
- [ ] Test reset while mappings exist.
- [ ] Test malicious or buggy DMA attempts.
- [ ] Provide a no-IOMMU restricted mode only with clear warning.

## 031. Synchronization, Atomics, and Concurrency

### 031.1 Atomic primitives

- [ ] Define atomic integer types.
- [ ] Define atomic pointer types.
- [ ] Implement load and store with explicit memory order.
- [ ] Implement exchange.
- [ ] Implement compare-and-exchange.
- [ ] Implement fetch-add and fetch-subtract.
- [ ] Implement bit test and modification operations.
- [ ] Implement reference-count primitives.
- [ ] Prevent reference-count overflow.
- [ ] Document x86 memory-order guarantees versus compiler ordering.
- [ ] Use portable compiler intrinsics where correct.
- [ ] Validate generated assembly for critical primitives.
- [ ] Provide litmus tests for memory ordering.

### 031.2 Locks

- [ ] Implement raw spinlock.
- [ ] Implement IRQ-disabling spinlock variants.
- [ ] Implement read-write spinlock only if justified.
- [ ] Implement sleepable mutex.
- [ ] Implement recursive locking policy or prohibit recursion.
- [ ] Implement read-write semaphore only if justified.
- [ ] Implement counting semaphore.
- [ ] Implement condition variable or wait queue.
- [ ] Implement completion event.
- [ ] Implement sequence lock where appropriate.
- [ ] Implement per-CPU synchronization helpers.
- [ ] Define lock ownership tracking.
- [ ] Define lock ranking.
- [ ] Detect lock-order inversion in debug builds.
- [ ] Detect recursive acquisition in debug builds.
- [ ] Detect unlock by non-owner.
- [ ] Detect sleeping while holding raw spinlock.
- [ ] Detect blocking in interrupt context.
- [ ] Implement priority inheritance for selected mutexes.
- [ ] Measure lock contention.
- [ ] Stress-test all lock primitives.

### 031.3 Read-mostly and lock-free mechanisms

- [ ] Define whether an RCU-like mechanism is required.
- [ ] Define grace-period detection.
- [ ] Define read-side critical sections.
- [ ] Define deferred reclamation.
- [ ] Implement hazard pointers or epoch reclamation if selected.
- [ ] Prove memory-reclamation safety.
- [ ] Document lock-free progress guarantees.
- [ ] Avoid lock-free designs without measurable benefit.
- [ ] Fuzz concurrent data structures.
- [ ] Run long-duration race stress tests.

## 032. Deferred Work, Work Queues, and Kernel Threads

- [ ] Define hard interrupt context.
- [ ] Define soft interrupt or bottom-half context.
- [ ] Define deferred procedure abstraction.
- [ ] Define per-CPU deferred queues.
- [ ] Define global work queues.
- [ ] Define ordered work queues.
- [ ] Define high-priority work queues.
- [ ] Define reclaim-safe work queues.
- [ ] Define delayed work.
- [ ] Define work cancellation.
- [ ] Define flush semantics.
- [ ] Handle cancellation racing with execution.
- [ ] Prevent queueing the same work item illegally.
- [ ] Detect work-queue deadlocks.
- [ ] Account worker runtime.
- [ ] Scale worker count under load.
- [ ] Limit runaway work creation.
- [ ] Create kernel thread abstraction.
- [ ] Create kernel thread stop protocol.
- [ ] Create kernel thread park and unpark protocol.
- [ ] Name kernel threads.
- [ ] Expose kernel thread state to diagnostics.

## 033. Scheduler

### 033.1 Scheduler model

- [ ] Define schedulable entity.
- [ ] Define task states.
- [ ] Define runnable state.
- [ ] Define running state.
- [ ] Define interruptible sleep.
- [ ] Define uninterruptible sleep.
- [ ] Define stopped state.
- [ ] Define zombie state.
- [ ] Define idle task per CPU.
- [ ] Define scheduler classes.
- [ ] Define normal class.
- [ ] Define real-time FIFO class if supported.
- [ ] Define real-time round-robin class if supported.
- [ ] Define deadline class if supported.
- [ ] Define background or idle class if supported.
- [ ] Define priority range.
- [ ] Define nice or weight mapping.
- [ ] Define time-slice rules.
- [ ] Define preemption model.
- [ ] Define wakeup-preemption rules.
- [ ] Define fairness guarantees.
- [ ] Define starvation bounds.
- [ ] Define CPU-affinity semantics.
- [ ] Define load-balancing domains.
- [ ] Define SMT-awareness policy.
- [ ] Define cache-topology awareness.
- [ ] Define NUMA awareness.
- [ ] Define power-awareness policy.
- [ ] Define thermal-awareness policy.
- [ ] Define scheduler accounting fields.

### 033.2 Run queues and dispatch

- [ ] Create per-CPU run queue.
- [ ] Choose run-queue data structure.
- [ ] Protect run queues with correct locking.
- [ ] Enqueue task.
- [ ] Dequeue task.
- [ ] Pick next task.
- [ ] Account execution time.
- [ ] Expire time slice.
- [ ] Trigger reschedule.
- [ ] Handle voluntary yield.
- [ ] Handle blocking.
- [ ] Handle wakeup.
- [ ] Handle task exit.
- [ ] Handle priority changes.
- [ ] Handle affinity changes.
- [ ] Handle CPU online and offline.
- [ ] Handle task migration.
- [ ] Avoid double enqueue.
- [ ] Avoid lost wakeups.
- [ ] Avoid scheduling dead tasks.
- [ ] Validate run-queue invariants in debug builds.
- [ ] Expose run-queue statistics.

### 033.3 Load balancing

- [ ] Define periodic balancing.
- [ ] Define idle balancing.
- [ ] Define wakeup placement.
- [ ] Define migration cost.
- [ ] Respect hard affinity.
- [ ] Respect real-time constraints.
- [ ] Prefer cache-local placement where beneficial.
- [ ] Avoid overloading one SMT sibling while cores are idle unless policy justifies it.
- [ ] Balance across core, cache, CCD, and NUMA domains.
- [ ] Avoid oscillatory migration.
- [ ] Account for task working-set behavior if measured.
- [ ] Measure balance overhead.
- [ ] Test asymmetric runnable loads.
- [ ] Test CPU-bound workloads.
- [ ] Test latency-sensitive workloads.
- [ ] Test mixed workloads.
- [ ] Test rapid wake-sleep workloads.

### 033.4 Preemption and scheduling entry points

- [ ] Define kernel preemption points.
- [ ] Define interrupt-exit rescheduling.
- [ ] Define syscall-exit rescheduling.
- [ ] Define blocking rescheduling.
- [ ] Define timer-driven rescheduling.
- [ ] Track preemption-disable count.
- [ ] Track interrupt-disable state.
- [ ] Prevent scheduling in atomic context.
- [ ] Prevent schedule recursion.
- [ ] Handle reschedule requests during context switch.
- [ ] Measure maximum preemption-disabled intervals.
- [ ] Add watchdog for scheduler stalls.

### 033.5 PDC scheduler research hook

- [ ] Keep a deterministic neutral scheduler available.
- [ ] Define a stable scheduler policy interface.
- [ ] Allow PDC policy to propose rather than directly force unsafe transitions.
- [ ] Validate every PDC scheduling action against affinity and privilege constraints.
- [ ] Validate starvation bounds.
- [ ] Validate deadline constraints.
- [ ] Validate real-time exclusions.
- [ ] Validate maximum intentional delay.
- [ ] Validate migration budget.
- [ ] Validate thermal constraints.
- [ ] Validate rollback trigger.
- [ ] Expire PDC decisions automatically.
- [ ] Fall back after policy crash.
- [ ] Fall back after watchdog timeout.
- [ ] Fall back after invariant violation.
- [ ] Record every policy input and output.
- [ ] Record setup and decision overhead.
- [ ] Record skipped decisions.
- [ ] Record fallback events.
- [ ] Support deterministic replay of scheduling decisions.
- [ ] Benchmark against neutral and conventional controls.
- [ ] Never report speedup without output-equivalence and total-cost checks.

## 034. Context Switching

- [ ] Define saved general-purpose register set.
- [ ] Define saved instruction pointer.
- [ ] Define saved stack pointer.
- [ ] Define saved flags.
- [ ] Define saved segment state.
- [ ] Define FS and GS base handling.
- [ ] Define FPU and extended-state handling.
- [ ] Define debug-register handling.
- [ ] Define performance-monitoring state handling.
- [ ] Define address-space switch.
- [ ] Define PCID switch behavior.
- [ ] Define kernel stack switch.
- [ ] Define TSS RSP0 update.
- [ ] Define per-CPU current-task update.
- [ ] Define speculation-mitigation hooks if required.
- [ ] Implement switch-to assembly.
- [ ] Annotate unwind information if supported.
- [ ] Verify stack alignment after switch.
- [ ] Verify callee-saved register preservation.
- [ ] Test rapid switching.
- [ ] Test migration between CPUs.
- [ ] Test switching tasks with different vector-state use.
- [ ] Test switching while signals are pending.
- [ ] Measure context-switch latency.

## 035. Process, Thread, and Task Model

### 035.1 Task objects

- [ ] Define task identifier type.
- [ ] Define process identifier type.
- [ ] Define thread identifier type.
- [ ] Define identifier allocation.
- [ ] Define identifier reuse delay.
- [ ] Define task reference counting.
- [ ] Define parent relationship.
- [ ] Define child list.
- [ ] Define process group.
- [ ] Define session.
- [ ] Define credentials pointer.
- [ ] Define address-space pointer.
- [ ] Define file-descriptor table pointer.
- [ ] Define signal state.
- [ ] Define scheduling state.
- [ ] Define resource-accounting state.
- [ ] Define namespace state if used.
- [ ] Define audit identity.
- [ ] Define executable identity.
- [ ] Define start time.
- [ ] Define exit status.
- [ ] Define wait state.
- [ ] Define task name.
- [ ] Define command line exposure.
- [ ] Define environment storage.
- [ ] Define current working directory.
- [ ] Define root directory.
- [ ] Define umask.
- [ ] Define resource limits.

### 035.2 Creation and termination

- [ ] Create initial kernel task.
- [ ] Create kernel threads.
- [ ] Create first user-space process.
- [ ] Implement process spawn.
- [ ] Implement thread creation.
- [ ] Implement address-space clone.
- [ ] Implement shared-address-space thread creation.
- [ ] Implement file-table inheritance.
- [ ] Implement credential inheritance.
- [ ] Implement signal disposition inheritance.
- [ ] Implement executable replacement.
- [ ] Implement process exit.
- [ ] Implement thread exit.
- [ ] Implement last-thread process cleanup.
- [ ] Implement zombie retention.
- [ ] Implement wait and reap.
- [ ] Implement orphan reparenting.
- [ ] Implement session-leader behavior.
- [ ] Implement process-group behavior.
- [ ] Implement exit notification.
- [ ] Release resources in safe order.
- [ ] Prevent identifier use-after-reuse.
- [ ] Test failure at every creation allocation step.

### 035.3 Resource limits and accounting

- [ ] Account user CPU time.
- [ ] Account kernel CPU time.
- [ ] Account elapsed time.
- [ ] Account context switches.
- [ ] Account page faults.
- [ ] Account resident memory.
- [ ] Account virtual memory.
- [ ] Account locked memory.
- [ ] Account open handles.
- [ ] Account threads.
- [ ] Account processes.
- [ ] Account file sizes.
- [ ] Account core-dump size.
- [ ] Account IPC resources.
- [ ] Account network usage if policy requires.
- [ ] Define per-process limits.
- [ ] Define per-user limits.
- [ ] Define system-wide limits.
- [ ] Enforce limits atomically.
- [ ] Expose limit query and update APIs.
- [ ] Audit privileged limit increases.

## 036. User/Kernel Transitions and System Call ABI

### 036.1 ABI definition

- [ ] Assign a system call ABI version.
- [ ] Choose SYSCALL/SYSRET as primary entry mechanism.
- [ ] Define system call number register.
- [ ] Define argument registers.
- [ ] Define return-value register.
- [ ] Define error reporting convention.
- [ ] Define clobbered registers.
- [ ] Define preserved registers.
- [ ] Define stack alignment.
- [ ] Define cancellation and restart semantics.
- [ ] Define 64-bit type layouts.
- [ ] Define time type widths.
- [ ] Define file-offset widths.
- [ ] Define object-handle widths.
- [ ] Define pointer validation rules.
- [ ] Define maximum copied structure sizes.
- [ ] Define versioned structure rules.
- [ ] Define unknown flag handling.
- [ ] Define reserved-field handling.
- [ ] Publish a machine-readable syscall table.
- [ ] Generate kernel dispatch tables.
- [ ] Generate user-space stubs.
- [ ] Generate documentation from the same source.

### 036.2 Entry path

- [ ] Configure STAR.
- [ ] Configure LSTAR.
- [ ] Configure SFMASK.
- [ ] Configure kernel GS base.
- [ ] Implement swapgs-safe entry.
- [ ] Save user RIP.
- [ ] Save user RFLAGS.
- [ ] Save user RSP.
- [ ] Switch to kernel stack.
- [ ] Build a uniform trap frame.
- [ ] Clear direction flag.
- [ ] Mask unsafe flags.
- [ ] Validate system call number.
- [ ] Validate each argument according to type.
- [ ] Perform capability checks.
- [ ] Dispatch without attacker-controlled indirect-call hazards where possible.
- [ ] Handle pending signals or exceptions.
- [ ] Handle rescheduling.
- [ ] Validate return RIP and RSP are canonical.
- [ ] Choose SYSRET or IRETQ safely.
- [ ] Restore user state.
- [ ] Test malicious register values.
- [ ] Test nested faults during entry and return.

### 036.3 User memory access

- [ ] Implement access-range validation.
- [ ] Implement copy from user.
- [ ] Implement copy to user.
- [ ] Implement string copy from user.
- [ ] Implement vector I/O copy helpers.
- [ ] Handle page faults during copy.
- [ ] Use exception fixup tables or equivalent.
- [ ] Prevent integer overflow in range checks.
- [ ] Prevent time-of-check/time-of-use assumptions about mutable user memory.
- [ ] Copy small control structures before validation.
- [ ] Pin or revalidate user pages for long operations.
- [ ] Respect SMAP when enabled.
- [ ] Return partial-copy results according to ABI.
- [ ] Fuzz all syscall pointer arguments.

## 037. Signals, Exceptions, Cancellation, and Process Events

- [ ] Define signal or process-exception number space.
- [ ] Define default action for each event.
- [ ] Define ignore behavior.
- [ ] Define catch behavior.
- [ ] Define nonmaskable events.
- [ ] Define blocked-signal mask.
- [ ] Define pending-signal queues.
- [ ] Define real-time queued events if supported.
- [ ] Define per-process and per-thread delivery.
- [ ] Define synchronous fault delivery.
- [ ] Define asynchronous event delivery.
- [ ] Define signal frame layout.
- [ ] Define alternate signal stack.
- [ ] Define user handler return trampoline.
- [ ] Validate user handler addresses.
- [ ] Validate signal-return frames against forgery.
- [ ] Save and restore vector state.
- [ ] Integrate interrupted system call restart.
- [ ] Integrate cancellation points if POSIX-like cancellation is supported.
- [ ] Implement child-state notifications.
- [ ] Implement terminal-generated events.
- [ ] Implement process stop and continue.
- [ ] Implement debugger-generated events.
- [ ] Test nested delivery.
- [ ] Test delivery during system calls.
- [ ] Test delivery during page faults.
- [ ] Test malicious signal frames.

## 038. Kernel Object, Handle, and File-Descriptor Model

- [ ] Define common kernel object header.
- [ ] Define object type identifier.
- [ ] Define object reference counting.
- [ ] Define object destruction rules.
- [ ] Define object naming policy.
- [ ] Define handle value format.
- [ ] Define handle table.
- [ ] Define handle rights mask.
- [ ] Define handle inheritance.
- [ ] Define close-on-exec behavior.
- [ ] Define duplicate-handle behavior.
- [ ] Define handle transfer through IPC.
- [ ] Prevent stale handle reuse attacks.
- [ ] Randomize or generation-tag handle values if needed.
- [ ] Implement file descriptor as a compatibility layer if desired.
- [ ] Implement descriptor flags.
- [ ] Implement status flags.
- [ ] Implement descriptor duplication.
- [ ] Implement descriptor table cloning.
- [ ] Implement atomic close-on-exec creation.
- [ ] Implement pollable-object interface.
- [ ] Expose handle leaks in diagnostics.
- [ ] Fuzz handle operations.

## 039. Inter-Process Communication

### 039.1 Pipes and streams

- [ ] Implement anonymous pipes.
- [ ] Implement named pipes if selected.
- [ ] Define pipe buffer capacity.
- [ ] Define atomic write size.
- [ ] Implement blocking reads.
- [ ] Implement blocking writes.
- [ ] Implement nonblocking mode.
- [ ] Implement end-of-file semantics.
- [ ] Implement broken-pipe notification.
- [ ] Implement poll readiness.
- [ ] Handle writer and reader closure races.
- [ ] Account pipe memory.

### 039.2 Shared memory

- [ ] Create shared-memory objects.
- [ ] Size shared-memory objects.
- [ ] Map shared-memory objects.
- [ ] Unmap shared-memory objects.
- [ ] Apply per-mapping protections.
- [ ] Support sealing if selected.
- [ ] Support anonymous shared mappings.
- [ ] Enforce ownership and permissions.
- [ ] Account resident pages.
- [ ] Handle object deletion while mapped.

### 039.3 Synchronization IPC

- [ ] Implement futex-like wait on user memory.
- [ ] Implement futex-like wake.
- [ ] Implement timeout.
- [ ] Implement private versus shared keys.
- [ ] Prevent lost wakeups.
- [ ] Handle process exit with robust locks if supported.
- [ ] Implement event objects.
- [ ] Implement semaphores.
- [ ] Implement completion ports or event queues if selected.
- [ ] Implement poll, select, or equivalent multiplexing.
- [ ] Implement edge-triggered and level-triggered semantics only with precise definitions.
- [ ] Test thundering-herd behavior.

### 039.4 Local sockets and RPC

- [ ] Implement local stream sockets.
- [ ] Implement local datagram sockets.
- [ ] Implement local sequenced-packet sockets if selected.
- [ ] Define socket address namespace.
- [ ] Support credential passing.
- [ ] Support handle passing.
- [ ] Support peer identity query.
- [ ] Enforce permissions on named endpoints.
- [ ] Define message framing.
- [ ] Define maximum message sizes.
- [ ] Define backpressure.
- [ ] Define cancellation.
- [ ] Define timeout.
- [ ] Define service discovery.
- [ ] Define RPC versioning.
- [ ] Define RPC authentication.
- [ ] Define RPC authorization.
- [ ] Define structured error responses.
- [ ] Generate client and server bindings if using an IDL.
- [ ] Fuzz RPC decoders.

## 040. Credentials, Identity, Permissions, and Access Control

- [ ] Define numeric user identifier.
- [ ] Define numeric group identifier.
- [ ] Define supplementary groups.
- [ ] Define kernel credentials object.
- [ ] Define real, effective, and saved identities if POSIX compatibility is desired.
- [ ] Define service identities.
- [ ] Define system identities.
- [ ] Define anonymous or nobody identity.
- [ ] Define root or superuser semantics.
- [ ] Minimize special-case superuser bypasses.
- [ ] Define capability-based privilege decomposition.
- [ ] Define inheritable capabilities.
- [ ] Define effective capabilities.
- [ ] Define permitted capabilities.
- [ ] Define ambient capabilities only if needed.
- [ ] Define privilege transition rules.
- [ ] Define set-user-ID and set-group-ID policy if supported.
- [ ] Define file ownership.
- [ ] Define mode permissions.
- [ ] Define access-control lists.
- [ ] Define default ACLs.
- [ ] Define mandatory access-control labels if selected.
- [ ] Define security contexts.
- [ ] Define object ownership transfer.
- [ ] Define permission checks at operation time.
- [ ] Define audit records for denied and privileged operations.
- [ ] Prevent confused-deputy behavior in services.
- [ ] Test identity changes across exec.
- [ ] Test credentials across IPC.
- [ ] Test permissions after rename and mount operations.

## 041. Namespaces, Isolation, and Resource Groups

- [ ] Decide whether process-ID namespaces are required.
- [ ] Decide whether mount namespaces are required.
- [ ] Decide whether network namespaces are required.
- [ ] Decide whether user namespaces are required.
- [ ] Decide whether IPC namespaces are required.
- [ ] Decide whether hostname namespaces are required.
- [ ] Define namespace object lifetime.
- [ ] Define namespace creation rights.
- [ ] Define namespace joining rights.
- [ ] Define namespace inheritance.
- [ ] Define cross-namespace handle rules.
- [ ] Define resource-control group hierarchy.
- [ ] Define CPU quota and weight controls.
- [ ] Define memory limits.
- [ ] Define I/O limits.
- [ ] Define process-count limits.
- [ ] Define device-access controls.
- [ ] Define network limits.
- [ ] Define accounting and pressure signals.
- [ ] Prevent resource-group escape.
- [ ] Test nested isolation.

## 042. Device Model and Driver Framework

### 042.1 Core device model

- [ ] Define bus object.
- [ ] Define device object.
- [ ] Define driver object.
- [ ] Define class object.
- [ ] Define device instance identifier.
- [ ] Define parent-child topology.
- [ ] Define hardware resources.
- [ ] Define MMIO resource.
- [ ] Define port-I/O resource.
- [ ] Define interrupt resource.
- [ ] Define DMA constraints.
- [ ] Define firmware node reference.
- [ ] Define device state machine.
- [ ] Define driver binding state machine.
- [ ] Define device presence state.
- [ ] Define power state.
- [ ] Define removal state.
- [ ] Define failed state.
- [ ] Define quarantined state.
- [ ] Implement device registration.
- [ ] Implement device unregistration.
- [ ] Implement driver registration.
- [ ] Implement driver unregistration.
- [ ] Implement ID-table matching.
- [ ] Implement firmware-node matching.
- [ ] Implement probe.
- [ ] Implement deferred probe.
- [ ] Implement remove.
- [ ] Implement shutdown callback.
- [ ] Implement suspend callback.
- [ ] Implement resume callback.
- [ ] Implement reset callback.
- [ ] Implement error-recovery callback.
- [ ] Expose device topology to user space.

### 042.2 Driver lifecycle safety

- [ ] Prevent binding multiple exclusive drivers.
- [ ] Reference devices during asynchronous work.
- [ ] Cancel work before removal.
- [ ] Disable interrupts before freeing handlers.
- [ ] Stop DMA before freeing buffers.
- [ ] Disable bus mastering before teardown.
- [ ] Wait for in-flight I/O.
- [ ] Invalidate user mappings on removal.
- [ ] Remove device nodes.
- [ ] Release MMIO mappings.
- [ ] Release I/O ports.
- [ ] Release interrupt vectors.
- [ ] Release DMA domains.
- [ ] Release firmware references.
- [ ] Handle surprise removal.
- [ ] Handle reset during active I/O.
- [ ] Handle suspend during active I/O.
- [ ] Handle resume failure.
- [ ] Quarantine repeatedly failing devices.
- [ ] Record lifecycle transitions.

### 042.3 User-visible device interfaces

- [ ] Define device-node namespace.
- [ ] Define stable device naming.
- [ ] Define dynamic device naming.
- [ ] Define device metadata query API.
- [ ] Define device property API.
- [ ] Define control operation API.
- [ ] Define asynchronous event API.
- [ ] Define memory-mapping policy.
- [ ] Define direct-I/O policy.
- [ ] Define access permissions.
- [ ] Define exclusive-open semantics.
- [ ] Define hotplug notification.
- [ ] Define driver-specific version negotiation.
- [ ] Fuzz control request decoders.

## 043. Firmware Blob and Microcode Loader

- [ ] Define firmware search paths.
- [ ] Define firmware package format.
- [ ] Define firmware manifest format.
- [ ] Define expected device identifiers.
- [ ] Define firmware version fields.
- [ ] Define firmware hashes.
- [ ] Define firmware signatures.
- [ ] Define compression support if needed.
- [ ] Load firmware from initramfs before root filesystem.
- [ ] Load firmware from system image after root mount.
- [ ] Cache firmware safely.
- [ ] Prevent path traversal.
- [ ] Prevent device-controlled arbitrary filenames without validation.
- [ ] Verify integrity before device upload.
- [ ] Enforce licensing and redistribution metadata.
- [ ] Log exact firmware version and hash.
- [ ] Handle missing firmware.
- [ ] Handle incompatible firmware.
- [ ] Handle upload timeout.
- [ ] Handle device rejection.
- [ ] Handle firmware-induced device reset.
- [ ] Prevent unprivileged firmware replacement.
- [ ] Support secure revocation of known-bad firmware.

## 044. ACPI Core and AML Execution

### 044.1 ACPI table discovery and validation

- [ ] Locate RSDP from UEFI configuration table.
- [ ] Validate RSDP signature.
- [ ] Validate RSDP revision.
- [ ] Validate RSDP checksums.
- [ ] Map XSDT.
- [ ] Fall back to RSDT only if required.
- [ ] Validate every table signature.
- [ ] Validate every table length.
- [ ] Validate every table checksum.
- [ ] Prevent integer overflow while mapping tables.
- [ ] Copy tables or retain mappings according to lifetime policy.
- [ ] Index tables by signature and instance.
- [ ] Preserve unknown tables for diagnostics.
- [ ] Expose raw tables to privileged diagnostics.
- [ ] Hash the table set in the hardware manifest.

### 044.2 Required and important ACPI tables

- [ ] Parse FADT.
- [ ] Parse DSDT pointer.
- [ ] Parse FACS pointer.
- [ ] Parse MADT.
- [ ] Parse MCFG.
- [ ] Parse HPET when present.
- [ ] Parse SRAT when present.
- [ ] Parse SLIT when present.
- [ ] Parse PPTT when present.
- [ ] Parse BGRT when present.
- [ ] Parse TPM2 when present.
- [ ] Parse SPCR when present.
- [ ] Parse GTDT only for future non-x86 targets.
- [ ] Parse IVRS on AMD IOMMU systems.
- [ ] Parse DMAR on future Intel IOMMU systems.
- [ ] Parse WDAT or watchdog tables when used.
- [ ] Parse EINJ only in controlled diagnostic builds.
- [ ] Parse ERST and HEST for hardware error reporting when implemented.
- [ ] Parse NFIT only if persistent memory is supported.
- [ ] Parse PCCT only if required by platform control channels.
- [ ] Parse CEDT only if future CXL support is added.
- [ ] Ignore unsupported tables safely.

### 044.3 AML interpreter

- [ ] Choose custom AML interpreter or ported ACPICA boundary.
- [ ] Parse AML bytecode safely.
- [ ] Build ACPI namespace.
- [ ] Support integer objects.
- [ ] Support string objects.
- [ ] Support buffer objects.
- [ ] Support package objects.
- [ ] Support fields.
- [ ] Support devices.
- [ ] Support methods.
- [ ] Support mutexes.
- [ ] Support events.
- [ ] Support operation regions.
- [ ] Support system memory operation regions.
- [ ] Support system I/O operation regions.
- [ ] Support PCI configuration operation regions.
- [ ] Support embedded-controller operation regions when needed.
- [ ] Support indexed fields.
- [ ] Support bank fields.
- [ ] Implement method argument and local storage.
- [ ] Implement control flow.
- [ ] Implement arithmetic and logical operations.
- [ ] Implement conversions.
- [ ] Implement references and dereferences.
- [ ] Implement object lifetime.
- [ ] Enforce AML execution limits.
- [ ] Enforce recursion limits.
- [ ] Enforce allocation limits.
- [ ] Enforce method timeouts.
- [ ] Serialize methods as specified.
- [ ] Prevent malformed AML from corrupting the kernel.
- [ ] Fuzz AML parser and evaluator.

### 044.4 ACPI namespace and device enumeration

- [ ] Evaluate `_HID`.
- [ ] Evaluate `_CID`.
- [ ] Evaluate `_UID`.
- [ ] Evaluate `_STA`.
- [ ] Evaluate `_ADR`.
- [ ] Evaluate `_CRS`.
- [ ] Evaluate `_PRS` only if resource reconfiguration is supported.
- [ ] Evaluate `_SRS` only under strict policy.
- [ ] Evaluate `_INI` at the correct stage.
- [ ] Evaluate `_DEP` dependencies.
- [ ] Evaluate `_CCA` cache-coherency information when applicable.
- [ ] Evaluate `_DSD` device properties.
- [ ] Evaluate `_DSM` only for known GUIDs and revisions.
- [ ] Evaluate `_OSC` ownership negotiation.
- [ ] Build firmware-node hierarchy.
- [ ] Create devices only when present and enabled.
- [ ] Resolve dependencies before probe.
- [ ] Handle namespace notifications.

### 044.5 ACPI interrupt, power, sleep, and thermal methods

- [ ] Evaluate PCI routing `_PRT`.
- [ ] Resolve link devices.
- [ ] Configure SCI interrupt.
- [ ] Handle fixed ACPI events.
- [ ] Handle general-purpose events.
- [ ] Handle power-button event.
- [ ] Handle sleep-button event if present.
- [ ] Handle RTC wake event if enabled.
- [ ] Handle thermal events.
- [ ] Implement `_S0` working state semantics.
- [ ] Implement `_S3` only after complete suspend/resume support.
- [ ] Implement `_S4` only after hibernation support.
- [ ] Implement `_S5` shutdown transition.
- [ ] Evaluate `_PTS` at correct time.
- [ ] Evaluate `_GTS` when required.
- [ ] Evaluate `_WAK` on resume.
- [ ] Evaluate device `_PS0`, `_PS1`, `_PS2`, and `_PS3` where supported.
- [ ] Evaluate `_PR0` through `_PR3` power resources.
- [ ] Evaluate `_PRW` wake capabilities.
- [ ] Parse thermal zones.
- [ ] Evaluate `_TMP`.
- [ ] Evaluate `_CRT`.
- [ ] Evaluate `_HOT`.
- [ ] Evaluate active and passive trip points.
- [ ] Never override critical thermal shutdown protections.
- [ ] Test shutdown and reboot repeatedly.

## 045. SMBIOS and Platform Identity

- [ ] Locate SMBIOS 3 entry point.
- [ ] Validate SMBIOS entry point.
- [ ] Fall back to SMBIOS 2 entry point if needed.
- [ ] Map structure table safely.
- [ ] Iterate structures with bounds checks.
- [ ] Parse BIOS information.
- [ ] Parse system information.
- [ ] Parse baseboard information.
- [ ] Parse chassis information.
- [ ] Parse processor information.
- [ ] Parse cache information.
- [ ] Parse memory array information.
- [ ] Parse memory device information.
- [ ] Parse memory mapped address information.
- [ ] Parse system boot information.
- [ ] Parse firmware inventory information when present.
- [ ] Preserve unknown structures.
- [ ] Sanitize strings before logging.
- [ ] Avoid trusting SMBIOS for security decisions.
- [ ] Use SMBIOS fields only as hardware-match inputs with fallbacks.
- [ ] Expose platform identity to privileged diagnostics.
- [ ] Hash relevant identity fields in compatibility receipts.

## 046. PCI and PCI Express Core

### 046.1 Configuration-space access

- [ ] Parse ACPI MCFG.
- [ ] Create ECAM segment mappings.
- [ ] Support multiple PCI segments.
- [ ] Support legacy configuration access only if explicitly needed.
- [ ] Validate bus ranges.
- [ ] Validate function numbers.
- [ ] Read vendor ID.
- [ ] Read device ID.
- [ ] Read command and status.
- [ ] Read revision and class codes.
- [ ] Read header type.
- [ ] Handle multifunction devices.
- [ ] Handle PCI-to-PCI bridges.
- [ ] Prevent out-of-range ECAM accesses.
- [ ] Serialize configuration writes.
- [ ] Expose safe diagnostic reads.
- [ ] Restrict configuration writes to kernel drivers.

### 046.2 Enumeration and topology

- [ ] Enumerate root buses.
- [ ] Enumerate all devices and functions.
- [ ] Traverse bridges.
- [ ] Read primary, secondary, and subordinate bus numbers.
- [ ] Handle firmware-configured bus numbering.
- [ ] Implement bus-number assignment only if needed.
- [ ] Build parent-child topology.
- [ ] Detect loops or malformed bridges.
- [ ] Record slot capabilities.
- [ ] Record link capabilities.
- [ ] Record negotiated link speed and width.
- [ ] Record device serial number capability when present.
- [ ] Record resizable BAR capability.
- [ ] Record ACS capability.
- [ ] Record ARI capability.
- [ ] Record ATS, PASID, and PRI only if used.
- [ ] Record PCIe error-reporting capability.
- [ ] Record power-management capability.
- [ ] Expose topology and capabilities to diagnostics.

### 046.3 BARs and resources

- [ ] Parse I/O BARs.
- [ ] Parse 32-bit memory BARs.
- [ ] Parse 64-bit memory BARs.
- [ ] Parse prefetchable BARs.
- [ ] Handle expansion ROM BARs under strict policy.
- [ ] Use firmware-assigned BAR addresses initially.
- [ ] Validate BAR alignment.
- [ ] Validate BAR size where safe to probe.
- [ ] Avoid destructive size probing on active devices.
- [ ] Map BARs with correct cacheability.
- [ ] Prevent overlapping resource claims.
- [ ] Track bridge windows.
- [ ] Support resizable BAR only after device-specific validation.
- [ ] Unmap resources on removal.

### 046.4 PCI capabilities

- [ ] Walk standard capability list with loop detection.
- [ ] Walk extended capability list with loop detection.
- [ ] Parse MSI.
- [ ] Parse MSI-X.
- [ ] Parse PCI Express capability.
- [ ] Parse power-management capability.
- [ ] Parse advanced error reporting.
- [ ] Parse virtual-channel capability only if needed.
- [ ] Parse device serial number.
- [ ] Parse resizable BAR.
- [ ] Parse L1 power-management substates only after validation.
- [ ] Parse vendor-specific capabilities without assuming format.
- [ ] Reject malformed capability pointers safely.

### 046.5 Bus mastering, reset, power, and error recovery

- [ ] Keep bus mastering disabled until driver initialization is safe.
- [ ] Enable memory-space decoding only when resources are mapped.
- [ ] Enable I/O-space decoding only when needed.
- [ ] Support function-level reset when advertised.
- [ ] Support secondary-bus reset under controlled conditions.
- [ ] Support device-specific reset.
- [ ] Implement D0 through D3 state transitions when safe.
- [ ] Handle surprise-down errors.
- [ ] Handle correctable errors.
- [ ] Handle nonfatal errors.
- [ ] Handle fatal errors.
- [ ] Log AER status.
- [ ] Clear handled error bits correctly.
- [ ] Quarantine devices after unrecoverable faults.
- [ ] Test reset with active interrupts and DMA disabled.

## 047. Block-Device Layer

- [ ] Define block-device object.
- [ ] Define logical sector size.
- [ ] Define physical sector size.
- [ ] Define optimal I/O size.
- [ ] Define alignment offset.
- [ ] Define capacity units.
- [ ] Define read request.
- [ ] Define write request.
- [ ] Define flush request.
- [ ] Define discard request.
- [ ] Define write-zeroes request.
- [ ] Define FUA semantics.
- [ ] Define barrier and ordering semantics.
- [ ] Define synchronous and asynchronous completion.
- [ ] Define request cancellation policy.
- [ ] Define timeout policy.
- [ ] Define retry policy.
- [ ] Define permanent error reporting.
- [ ] Define removable-device behavior.
- [ ] Create request queue.
- [ ] Merge adjacent requests only when semantics permit.
- [ ] Split requests at device limits.
- [ ] Respect maximum transfer size.
- [ ] Respect segment limits.
- [ ] Respect boundary limits.
- [ ] Map scatter-gather lists.
- [ ] Track in-flight requests.
- [ ] Implement per-device queue freeze.
- [ ] Implement drain operation.
- [ ] Implement shutdown flush.
- [ ] Implement device removal handling.
- [ ] Expose latency and throughput statistics.
- [ ] Expose error counters.
- [ ] Inject I/O failures for tests.

## 048. Partition Tables and Volume Discovery

- [ ] Implement GPT parser.
- [ ] Validate GPT signature.
- [ ] Validate header revision.
- [ ] Validate header size.
- [ ] Validate header CRC.
- [ ] Validate partition-array CRC.
- [ ] Validate current and backup LBA fields.
- [ ] Validate usable LBA range.
- [ ] Validate entry size and count.
- [ ] Prevent multiplication overflow.
- [ ] Validate partition ranges.
- [ ] Detect overlapping partitions.
- [ ] Decode partition type GUID.
- [ ] Decode unique partition GUID.
- [ ] Decode UTF-16 partition name.
- [ ] Prefer valid primary GPT.
- [ ] Recover from valid backup GPT only under explicit policy.
- [ ] Report mismatched primary and backup GPT.
- [ ] Implement protective MBR parser.
- [ ] Implement legacy MBR parser only if selected.
- [ ] Detect extended partitions only if selected.
- [ ] Create partition block devices.
- [ ] Notify user space of volume appearance.
- [ ] Support removable-media re-scan.
- [ ] Never auto-mount unknown filesystems as writable by default.

## 049. NVMe Driver

### 049.1 Controller discovery and register access

- [ ] Match NVMe PCI class code.
- [ ] Map controller BAR.
- [ ] Read controller capabilities.
- [ ] Validate doorbell stride.
- [ ] Validate memory page size range.
- [ ] Validate timeout value.
- [ ] Validate queue entry size capabilities.
- [ ] Read version register.
- [ ] Read controller configuration.
- [ ] Read controller status.
- [ ] Disable controller before reinitialization.
- [ ] Wait for ready transition with timeout.
- [ ] Handle fatal status.
- [ ] Configure memory page size.
- [ ] Configure arbitration method.
- [ ] Configure command set.
- [ ] Configure admin queue entry sizes.

### 049.2 Admin queue

- [ ] Allocate physically suitable admin submission queue.
- [ ] Allocate physically suitable admin completion queue.
- [ ] Zero queue memory.
- [ ] Program admin queue attributes.
- [ ] Program admin queue base addresses.
- [ ] Enable controller.
- [ ] Wait for controller ready.
- [ ] Implement submission tail tracking.
- [ ] Implement completion head tracking.
- [ ] Implement phase-tag handling.
- [ ] Ring doorbells with correct stride.
- [ ] Assign command identifiers.
- [ ] Track outstanding admin commands.
- [ ] Handle completion status.
- [ ] Handle command timeout.
- [ ] Abort commands when supported.
- [ ] Reset controller after unrecoverable timeout.
- [ ] Use MSI-X for admin completion when available.
- [ ] Support polling during earliest bootstrap.

### 049.3 Identification and feature setup

- [ ] Issue Identify Controller.
- [ ] Validate returned structure length.
- [ ] Record serial number safely.
- [ ] Record model number safely.
- [ ] Record firmware revision safely.
- [ ] Record maximum data transfer size.
- [ ] Record namespace count.
- [ ] Record optional command support.
- [ ] Record volatile write cache support.
- [ ] Record sanitize support but disable destructive use by default.
- [ ] Record firmware update support but disable by default.
- [ ] Record power-state descriptors.
- [ ] Record submission and completion queue entry sizes.
- [ ] Issue Identify Namespace for each active namespace.
- [ ] Record namespace capacity.
- [ ] Record namespace utilization.
- [ ] Record formatted LBA size.
- [ ] Record metadata format.
- [ ] Reject unsupported metadata configurations.
- [ ] Record deallocation support.
- [ ] Record namespace GUID and EUI-64.
- [ ] Configure number of I/O queues.
- [ ] Configure interrupt coalescing only after baseline correctness.
- [ ] Configure volatile write cache policy.
- [ ] Configure asynchronous event requests.

### 049.4 I/O queues and commands

- [ ] Allocate I/O completion queues.
- [ ] Allocate I/O submission queues.
- [ ] Bind queues to interrupt vectors.
- [ ] Create queues with admin commands.
- [ ] Create per-CPU or per-core queue mapping.
- [ ] Implement read command.
- [ ] Implement write command.
- [ ] Implement flush command.
- [ ] Implement dataset management deallocate.
- [ ] Implement write zeroes only if supported.
- [ ] Build PRP lists.
- [ ] Handle unaligned first and last pages.
- [ ] Handle transfers requiring multiple PRP list pages.
- [ ] Support SGLs only after PRPs are stable.
- [ ] Respect maximum transfer size.
- [ ] Respect namespace LBA boundaries.
- [ ] Validate command completion status codes.
- [ ] Map errors to block-layer status.
- [ ] Handle queue full.
- [ ] Handle command abort.
- [ ] Handle controller reset with outstanding I/O.
- [ ] Recreate queues after reset.
- [ ] Test queue wraparound.
- [ ] Test command identifier wraparound.

### 049.5 Shutdown, health, and error handling

- [ ] Issue flush before orderly shutdown when required.
- [ ] Set normal shutdown notification.
- [ ] Wait for shutdown complete with timeout.
- [ ] Handle abrupt shutdown state on next boot.
- [ ] Read SMART and health log.
- [ ] Read error information log.
- [ ] Read firmware slot information.
- [ ] Track critical warnings.
- [ ] Track media errors.
- [ ] Track unsafe shutdown count.
- [ ] Track temperature.
- [ ] Track percentage used.
- [ ] Track available spare.
- [ ] Handle namespace change asynchronous events.
- [ ] Handle firmware activation events only under controlled update flow.
- [ ] Implement controller reset state machine.
- [ ] Implement PCI function reset fallback.
- [ ] Quarantine device after repeated fatal errors.
- [ ] Preserve diagnostic logs before reset.
- [ ] Power-loss test write ordering.
- [ ] Verify flush and FUA semantics experimentally on sacrificial hardware.

## 050. AHCI, SATA, and ATAPI Optional Storage Path

- [ ] Match AHCI PCI class code.
- [ ] Map AHCI BAR.
- [ ] Read host capabilities.
- [ ] Perform BIOS/OS handoff when required.
- [ ] Reset HBA safely.
- [ ] Enumerate implemented ports.
- [ ] Detect device signatures.
- [ ] Allocate command list.
- [ ] Allocate received FIS area.
- [ ] Allocate command tables.
- [ ] Configure DMA addresses.
- [ ] Start and stop command engine correctly.
- [ ] Implement IDENTIFY DEVICE.
- [ ] Parse capacity and sector sizes.
- [ ] Implement DMA read.
- [ ] Implement DMA write.
- [ ] Implement flush cache.
- [ ] Implement NCQ only after non-NCQ correctness.
- [ ] Handle port interrupts.
- [ ] Handle task-file errors.
- [ ] Handle link changes.
- [ ] Handle hotplug only if supported.
- [ ] Reset failed ports.
- [ ] Implement TRIM if supported.
- [ ] Implement ATAPI packet commands only if optical media is required.
- [ ] Test 512-byte and 4-KiB logical sectors.
- [ ] Test power loss and error recovery.

## 051. USB Core Architecture

### 051.1 USB object model

- [ ] Define USB host controller object.
- [ ] Define USB root hub object.
- [ ] Define USB hub object.
- [ ] Define USB device object.
- [ ] Define USB configuration object.
- [ ] Define USB interface object.
- [ ] Define USB alternate-setting object.
- [ ] Define USB endpoint object.
- [ ] Define USB transfer request.
- [ ] Define USB pipe identity.
- [ ] Define USB speed enumeration.
- [ ] Define device address allocation.
- [ ] Define device state machine.
- [ ] Define enumeration state machine.
- [ ] Define disconnect state machine.
- [ ] Define driver-interface binding.
- [ ] Define composite-device handling.
- [ ] Define interface association handling.
- [ ] Define class-driver registration.
- [ ] Define vendor-specific driver registration.
- [ ] Define transfer timeout semantics.
- [ ] Define transfer cancellation semantics.
- [ ] Define short-packet semantics.
- [ ] Define stall recovery.
- [ ] Define bandwidth reservation.
- [ ] Define periodic scheduling policy.

### 051.2 Descriptor parsing

- [ ] Parse device descriptor.
- [ ] Parse device qualifier descriptor when relevant.
- [ ] Parse configuration descriptor.
- [ ] Parse interface descriptor.
- [ ] Parse endpoint descriptor.
- [ ] Parse string descriptors.
- [ ] Parse binary object store descriptor when supported.
- [ ] Parse interface association descriptor.
- [ ] Parse SuperSpeed endpoint companion descriptor.
- [ ] Parse SuperSpeedPlus companion descriptor when supported.
- [ ] Validate every descriptor length.
- [ ] Validate total configuration length.
- [ ] Reject zero-length descriptor loops.
- [ ] Reject descriptors extending beyond transfer data.
- [ ] Validate endpoint numbers and directions.
- [ ] Validate endpoint types.
- [ ] Validate maximum packet sizes.
- [ ] Validate interval values.
- [ ] Handle unknown descriptors by skipping safely.
- [ ] Preserve class-specific descriptors for class drivers.
- [ ] Sanitize untrusted strings.
- [ ] Fuzz all descriptor parsers.

### 051.3 Transfer types

- [ ] Implement control transfers.
- [ ] Implement setup stage.
- [ ] Implement data stage.
- [ ] Implement status stage.
- [ ] Implement bulk transfers.
- [ ] Implement interrupt transfers.
- [ ] Implement isochronous transfers only when audio or video requires them.
- [ ] Implement synchronous transfer API.
- [ ] Implement asynchronous transfer API.
- [ ] Implement scatter-gather support if host controller permits.
- [ ] Implement transfer cancellation.
- [ ] Implement timeout.
- [ ] Implement endpoint halt clear.
- [ ] Implement device reset.
- [ ] Implement endpoint reset.
- [ ] Track transfer ownership.
- [ ] Prevent use-after-disconnect.
- [ ] Account transfer bytes and errors.

### 051.4 Enumeration

- [ ] Detect port connect.
- [ ] Debounce connection.
- [ ] Reset port.
- [ ] Determine speed.
- [ ] Use default address zero.
- [ ] Read initial device descriptor bytes.
- [ ] Set maximum packet size for endpoint zero.
- [ ] Allocate unique address.
- [ ] Send Set Address.
- [ ] Wait required recovery time.
- [ ] Read full device descriptor.
- [ ] Read configuration descriptors.
- [ ] Read required string descriptors.
- [ ] Select a supported configuration.
- [ ] Send Set Configuration.
- [ ] Enumerate interfaces.
- [ ] Bind class or vendor drivers.
- [ ] Handle devices with no supported interfaces.
- [ ] Handle enumeration timeout.
- [ ] Handle disconnect during enumeration.
- [ ] Retry only within bounded policy.
- [ ] Log exact failure stage.

## 052. xHCI Host Controller Driver

### 052.1 Controller initialization

- [ ] Match xHCI PCI class code.
- [ ] Map xHCI capability and operational registers.
- [ ] Read capability length.
- [ ] Read interface version.
- [ ] Read structural parameters.
- [ ] Read capability parameters.
- [ ] Read doorbell offset.
- [ ] Read runtime-register offset.
- [ ] Walk extended capabilities safely.
- [ ] Perform BIOS/OS ownership handoff.
- [ ] Halt controller.
- [ ] Reset controller.
- [ ] Wait for controller not ready to clear.
- [ ] Select maximum device slots.
- [ ] Allocate device context base address array.
- [ ] Allocate scratchpad buffers when required.
- [ ] Allocate command ring.
- [ ] Initialize command ring cycle state.
- [ ] Allocate event ring segments.
- [ ] Create event ring segment table.
- [ ] Program event ring dequeue pointer.
- [ ] Program command ring control register.
- [ ] Program DCBAA pointer.
- [ ] Configure interrupter zero.
- [ ] Enable controller.
- [ ] Wait for running state.
- [ ] Enumerate root-hub ports.

### 052.2 Rings and transfer request blocks

- [ ] Define TRB structure and field helpers.
- [ ] Implement producer cycle-state handling.
- [ ] Implement consumer cycle-state handling.
- [ ] Implement link TRBs.
- [ ] Implement no-op command TRB.
- [ ] Implement enable-slot command.
- [ ] Implement disable-slot command.
- [ ] Implement address-device command.
- [ ] Implement configure-endpoint command.
- [ ] Implement evaluate-context command.
- [ ] Implement reset-endpoint command.
- [ ] Implement stop-endpoint command.
- [ ] Implement set-dequeue-pointer command.
- [ ] Implement reset-device command.
- [ ] Track command completion by pointer or token.
- [ ] Allocate transfer rings per endpoint.
- [ ] Build normal TRBs.
- [ ] Build setup-stage TRBs.
- [ ] Build data-stage TRBs.
- [ ] Build status-stage TRBs.
- [ ] Build isochronous TRBs only if required.
- [ ] Build event-data TRBs if selected.
- [ ] Ring endpoint doorbells.
- [ ] Handle ring wraparound.
- [ ] Prevent ring overrun.
- [ ] Recover from command-ring stopped or aborted state.

### 052.3 Device and endpoint contexts

- [ ] Determine context size.
- [ ] Allocate input context.
- [ ] Allocate output device context.
- [ ] Initialize slot context.
- [ ] Initialize endpoint zero context.
- [ ] Calculate route string.
- [ ] Set root-hub port number.
- [ ] Set device speed.
- [ ] Set context entries.
- [ ] Set maximum packet size.
- [ ] Set interval encoding.
- [ ] Set endpoint type.
- [ ] Set maximum burst.
- [ ] Set dequeue pointer and cycle state.
- [ ] Configure endpoint contexts after Set Configuration.
- [ ] Update contexts after alternate setting.
- [ ] Drop endpoint contexts on interface change.
- [ ] Validate context alignment and physical-address constraints.

### 052.4 Event handling

- [ ] Handle command-completion events.
- [ ] Handle transfer events.
- [ ] Handle port-status-change events.
- [ ] Handle host-controller events.
- [ ] Handle device-notification events if used.
- [ ] Handle bandwidth-request events if used.
- [ ] Handle event-ring-full condition.
- [ ] Decode completion codes.
- [ ] Match transfers to requests.
- [ ] Report residual lengths.
- [ ] Handle short packets.
- [ ] Handle stalls.
- [ ] Handle transaction errors.
- [ ] Handle babble errors.
- [ ] Handle missed service errors.
- [ ] Advance event-ring dequeue pointer.
- [ ] Acknowledge interrupter.
- [ ] Support multiple interrupters only after basic stability.
- [ ] Collect per-port and per-endpoint error statistics.

### 052.5 Root hub and port management

- [ ] Represent USB 2 and USB 3 root-hub ports correctly.
- [ ] Parse supported-protocol extended capabilities.
- [ ] Map port numbers to protocol groups.
- [ ] Read port status.
- [ ] Handle connect-status change.
- [ ] Handle port-enable change.
- [ ] Handle warm reset when required.
- [ ] Handle link-state change.
- [ ] Handle overcurrent.
- [ ] Handle port power if controllable.
- [ ] Clear change bits correctly.
- [ ] Implement debounce timers.
- [ ] Implement port reset.
- [ ] Implement device disconnect teardown.
- [ ] Implement controller suspend and resume only after tested.
- [ ] Test USB 2, USB 3, hubs, and rapid reconnect.

## 053. USB Hub Driver

- [ ] Match hub class interfaces.
- [ ] Read hub descriptor.
- [ ] Determine port count.
- [ ] Determine power-switching mode.
- [ ] Determine overcurrent mode.
- [ ] Power ports when required.
- [ ] Wait power-good delay.
- [ ] Allocate interrupt status endpoint transfer.
- [ ] Parse port-change bitmap.
- [ ] Read port status.
- [ ] Clear port change features.
- [ ] Reset downstream port.
- [ ] Determine downstream device speed.
- [ ] Create child device topology.
- [ ] Handle nested hubs.
- [ ] Handle multi-transaction-translator hubs if USB 2 split transactions are relevant.
- [ ] Handle hub disconnect with child teardown.
- [ ] Handle overcurrent safely.
- [ ] Rate-limit flapping ports.
- [ ] Test bus-powered and self-powered hubs.

## 054. USB HID, Keyboard, Mouse, and Input Core

### 054.1 HID parser

- [ ] Match HID interfaces.
- [ ] Read HID descriptor.
- [ ] Read report descriptor.
- [ ] Parse main items.
- [ ] Parse global items.
- [ ] Parse local items.
- [ ] Maintain global push and pop stack.
- [ ] Track usage pages.
- [ ] Track usages and usage ranges.
- [ ] Track report IDs.
- [ ] Track report sizes and counts.
- [ ] Track logical and physical ranges.
- [ ] Track units and unit exponents.
- [ ] Construct input field definitions.
- [ ] Construct output field definitions.
- [ ] Construct feature field definitions.
- [ ] Reject descriptor arithmetic overflow.
- [ ] Reject excessive nesting.
- [ ] Reject excessive report sizes.
- [ ] Handle unknown usages safely.
- [ ] Fuzz report descriptor parser.

### 054.2 Boot keyboard

- [ ] Support HID boot protocol keyboard.
- [ ] Select boot protocol when required.
- [ ] Set idle rate when useful.
- [ ] Submit recurring interrupt-IN transfers.
- [ ] Decode modifier byte.
- [ ] Decode key array.
- [ ] Track press and release transitions.
- [ ] Handle rollover error codes.
- [ ] Map USB usages to internal key codes.
- [ ] Maintain lock-key state.
- [ ] Send LED output reports.
- [ ] Support repeat in the input layer rather than driver when possible.
- [ ] Handle disconnect with synthetic key releases.
- [ ] Test multiple simultaneous keys.

### 054.3 Mouse and pointer

- [ ] Support HID boot protocol mouse.
- [ ] Parse relative X movement.
- [ ] Parse relative Y movement.
- [ ] Parse wheel movement.
- [ ] Parse buttons.
- [ ] Support high-resolution wheel usages when present.
- [ ] Support additional buttons through generic HID reports.
- [ ] Clamp malformed values.
- [ ] Accumulate pointer events.
- [ ] Handle disconnect with button releases.
- [ ] Expose raw and accelerated motion separately.

### 054.4 Generic input subsystem

- [ ] Define input device object.
- [ ] Define key event.
- [ ] Define relative-axis event.
- [ ] Define absolute-axis event.
- [ ] Define switch event.
- [ ] Define touch event.
- [ ] Define game-controller event.
- [ ] Define timestamp semantics.
- [ ] Define device capability query.
- [ ] Define event queue.
- [ ] Define event overflow behavior.
- [ ] Define exclusive grab.
- [ ] Define synthetic input privilege.
- [ ] Define keymap layer.
- [ ] Define compose layer.
- [ ] Define repeat behavior.
- [ ] Define pointer acceleration policy.
- [ ] Define multi-seat support if needed.
- [ ] Define secure-attention sequence.
- [ ] Prevent unprivileged injection into secure sessions.
- [ ] Expose hotplug events.

## 055. USB Mass Storage and SCSI Translation

### 055.1 Bulk-Only Transport

- [ ] Match USB mass-storage class and BOT protocol.
- [ ] Select bulk IN endpoint.
- [ ] Select bulk OUT endpoint.
- [ ] Build command block wrapper.
- [ ] Assign transfer tag.
- [ ] Send command payload.
- [ ] Transfer data phase.
- [ ] Read command status wrapper.
- [ ] Validate signature.
- [ ] Validate tag.
- [ ] Validate residue.
- [ ] Handle passed status.
- [ ] Handle failed status.
- [ ] Handle phase error.
- [ ] Issue bulk-only reset recovery.
- [ ] Clear endpoint halts.
- [ ] Retry within bounded policy.
- [ ] Handle disconnect during command.

### 055.2 SCSI command subset

- [ ] Implement INQUIRY.
- [ ] Implement TEST UNIT READY.
- [ ] Implement REQUEST SENSE.
- [ ] Implement READ CAPACITY(10).
- [ ] Implement READ CAPACITY(16).
- [ ] Implement READ(10).
- [ ] Implement READ(16).
- [ ] Implement WRITE(10).
- [ ] Implement WRITE(16).
- [ ] Implement SYNCHRONIZE CACHE.
- [ ] Implement MODE SENSE only if needed.
- [ ] Implement START STOP UNIT only if needed.
- [ ] Parse fixed and descriptor sense data.
- [ ] Map sense keys to block-layer errors.
- [ ] Handle unit attention.
- [ ] Handle not ready.
- [ ] Handle medium changed.
- [ ] Handle write protection.
- [ ] Handle removable media.
- [ ] Validate sector sizes and capacity.

### 055.3 USB Attached SCSI optional path

- [ ] Parse UAS interface descriptors.
- [ ] Require stream support where mandated.
- [ ] Implement command IU.
- [ ] Implement response IU.
- [ ] Implement sense IU.
- [ ] Implement task management IU.
- [ ] Map commands to USB streams.
- [ ] Handle out-of-order completion.
- [ ] Handle task abort.
- [ ] Handle logical unit reset.
- [ ] Fall back to BOT only when device provides an alternate BOT interface.
- [ ] Quirk devices with broken UAS behavior using evidence-backed entries.

## 056. Additional USB Classes

- [ ] Implement USB CDC ACM only if serial adapters or modems are needed.
- [ ] Implement CDC Ethernet Control Model only if a target adapter requires it.
- [ ] Implement CDC Network Control Model only if a target adapter requires it.
- [ ] Implement USB audio control class only after isochronous support.
- [ ] Implement USB audio streaming class only after clock-domain handling.
- [ ] Implement USB MIDI only if required.
- [ ] Implement USB Bluetooth HCI transport for target adapters.
- [ ] Implement USB printer class only if printing is a product goal.
- [ ] Implement USB video class only if webcams are a product goal.
- [ ] Implement USB DFU only in a tightly controlled update utility.
- [ ] Implement USB smart-card class only if required.
- [ ] Implement vendor-specific devices only with explicit drivers.
- [ ] Create a deny or quarantine policy for untrusted USB classes.
- [ ] Create user-visible authorization for newly attached sensitive devices.

## 057. Legacy PS/2 and Simple Recovery Input

- [ ] Decide whether i8042 support is required.
- [ ] Detect controller availability without hanging firmware.
- [ ] Disable ports during initialization.
- [ ] Flush output buffer.
- [ ] Configure controller byte.
- [ ] Self-test controller.
- [ ] Test keyboard port.
- [ ] Test auxiliary port.
- [ ] Enable required ports.
- [ ] Reset keyboard.
- [ ] Select scan-code set.
- [ ] Enable scanning.
- [ ] Decode make and break sequences.
- [ ] Handle extended prefixes.
- [ ] Handle Pause and Print Screen sequences.
- [ ] Reset mouse.
- [ ] Detect wheel mouse extensions if desired.
- [ ] Route IRQ1 and IRQ12.
- [ ] Keep PS/2 disabled when absent or unreliable.
- [ ] Use only as a recovery path on supported boards.

## 058. Display Bootstrap and Software Graphics

### 058.1 Firmware framebuffer

- [ ] Retain UEFI GOP framebuffer mapping after ExitBootServices.
- [ ] Validate framebuffer physical range.
- [ ] Validate scanline stride.
- [ ] Validate pixel format.
- [ ] Implement pixel packing for RGB reserved 8-bit formats.
- [ ] Implement pixel packing for BGR reserved 8-bit formats.
- [ ] Implement arbitrary bitmask formats.
- [ ] Reject unsupported BLT-only modes after boot.
- [ ] Map framebuffer write-combining when safe.
- [ ] Implement bounded pixel write.
- [ ] Implement rectangle fill.
- [ ] Implement rectangle copy with overlap handling.
- [ ] Implement image blit.
- [ ] Implement line drawing for diagnostics.
- [ ] Implement simple bitmap font renderer.
- [ ] Implement scrolling console.
- [ ] Implement dirty-rectangle tracking.
- [ ] Implement double-buffered software surface.
- [ ] Copy only dirty regions to framebuffer.
- [ ] Measure copy bandwidth and latency.
- [ ] Protect framebuffer from unprivileged direct writes after window system starts.

### 058.2 Display identification and modes

- [ ] Obtain EDID through GPU display hardware when a native driver exists.
- [ ] Parse EDID base block.
- [ ] Validate EDID checksum.
- [ ] Parse manufacturer and product identifiers.
- [ ] Parse basic display parameters.
- [ ] Parse established timings.
- [ ] Parse standard timings.
- [ ] Parse detailed timing descriptors.
- [ ] Parse display name.
- [ ] Parse range limits.
- [ ] Parse CTA-861 extension when implemented.
- [ ] Parse DisplayID extension when implemented.
- [ ] Parse HDR metadata when implemented.
- [ ] Parse variable-refresh capability when implemented.
- [ ] Preserve unknown extension blocks.
- [ ] Reject malformed length and timing arithmetic.
- [ ] Select safe fallback mode.
- [ ] Maintain exact pixel clock and blanking values.
- [ ] Do not program modes until hardware-specific display engine is understood.

### 058.3 Software renderer

- [ ] Define canonical internal pixel format.
- [ ] Implement premultiplied-alpha compositing.
- [ ] Implement source-over blending.
- [ ] Implement nearest-neighbor scaling.
- [ ] Implement bilinear scaling if needed.
- [ ] Implement clipping regions.
- [ ] Implement transformed blits only after basic operations.
- [ ] Implement solid fills.
- [ ] Implement gradients only if UI requires them.
- [ ] Implement image decode through audited user-space libraries or custom decoders.
- [ ] Use SIMD only behind tested scalar reference paths.
- [ ] Validate arithmetic overflow for surface dimensions and strides.
- [ ] Sandbox complex image decoders.
- [ ] Benchmark scalar and vector paths for correctness and total cost.

## 059. Native GPU and Display Driver Framework

- [ ] Define GPU device object.
- [ ] Define display controller object.
- [ ] Define connector object.
- [ ] Define encoder object.
- [ ] Define CRTC or scanout engine object.
- [ ] Define plane object.
- [ ] Define framebuffer object.
- [ ] Define display mode object.
- [ ] Define atomic display-state object.
- [ ] Define graphics memory object.
- [ ] Define GPU virtual-address space.
- [ ] Define command queue.
- [ ] Define synchronization object.
- [ ] Define fence and timeline semantics.
- [ ] Define buffer-sharing handle.
- [ ] Define user-space graphics-driver boundary.
- [ ] Define kernel-mode display-driver boundary.
- [ ] Define modeset ownership.
- [ ] Define master or lease semantics.
- [ ] Define hotplug event semantics.
- [ ] Define GPU reset semantics.
- [ ] Define process isolation semantics.
- [ ] Define hang detection.
- [ ] Define command validation or trusted-user-driver model.
- [ ] Define firmware loading.
- [ ] Define power and clock management boundary.
- [ ] Define thermal and fan safety boundary.
- [ ] Define video-memory eviction policy.
- [ ] Define system-memory pinning policy.
- [ ] Define IOMMU integration.
- [ ] Define multi-monitor support.
- [ ] Define suspend and resume behavior.
- [ ] Create a software-only conformance backend.

## 060. NVIDIA RTX 5070 Driver Research Workstream

- [ ] Record exact PCI identifiers and VBIOS hash.
- [ ] Record GPU architecture and chip revision from public or lawfully obtained sources.
- [ ] Identify all BARs and their sizes.
- [ ] Identify resizable-BAR behavior.
- [ ] Identify VGA compatibility state.
- [ ] Identify firmware-provided GOP behavior.
- [ ] Identify publicly documented firmware interfaces.
- [ ] Identify required signed firmware and microcode components.
- [ ] Determine whether firmware redistribution is permitted.
- [ ] Determine whether firmware can initialize the device without vendor operating-system code.
- [ ] Determine whether public NVIDIA open-kernel-module source contains reusable knowledge without importing Linux dependencies.
- [ ] Separate interface knowledge from Linux-specific implementation.
- [ ] Establish a clean-room process if reverse engineering is required.
- [ ] Seek vendor documentation or partnership for undocumented interfaces.
- [ ] Implement safe PCI enablement without touching unknown registers.
- [ ] Implement device reset path.
- [ ] Implement interrupt discovery and masking.
- [ ] Implement MMIO trace infrastructure in a controlled test environment.
- [ ] Map VRAM apertures only after bounds are understood.
- [ ] Identify GPU system processor boot requirements.
- [ ] Identify memory-controller initialization ownership.
- [ ] Identify GPU virtual-memory page-table format.
- [ ] Identify channel and runlist model.
- [ ] Identify command submission packet format.
- [ ] Identify copy engine behavior.
- [ ] Identify graphics engine behavior.
- [ ] Identify compute engine behavior.
- [ ] Identify display engine behavior.
- [ ] Identify connector and encoder routing.
- [ ] Identify hotplug interrupt behavior.
- [ ] Identify scanout surface format and tiling.
- [ ] Identify clock and power-state control.
- [ ] Identify thermal sensors and critical limits.
- [ ] Identify fan-control ownership.
- [ ] Identify GPU reset and recovery sequence.
- [ ] Implement read-only telemetry before actuation.
- [ ] Implement framebuffer handoff without native modesetting as the first usable stage.
- [ ] Implement modesetting only on one connector and one known mode initially.
- [ ] Implement scanout from a linear system or VRAM buffer.
- [ ] Implement cursor plane only after stable scanout.
- [ ] Implement page flip and vblank events.
- [ ] Implement memory allocation and mapping.
- [ ] Implement per-process GPU address spaces.
- [ ] Implement command buffer allocation.
- [ ] Implement command validation or trusted privileged submission service.
- [ ] Implement fences and synchronization.
- [ ] Implement copy engine before 3D where feasible.
- [ ] Implement shader compiler or SPIR-V translation only after command submission is stable.
- [ ] Implement Vulkan user-space driver only after kernel interfaces are stable.
- [ ] Implement OpenGL through a translation layer only after Vulkan or equivalent is stable.
- [ ] Implement CUDA compatibility only with vendor cooperation or independently specified ABI.
- [ ] Do not expose undocumented power or voltage writes in production.
- [ ] Do not permit automatic PDC GPU actuation before reset, watchdog, and thermal fallbacks are proven.
- [ ] Maintain permanent GOP safe mode independent of native driver.

## 061. Graphics APIs, Shader Toolchain, and Window-System Integration

- [ ] Define the native PooleOS graphics API.
- [ ] Decide whether Vulkan compatibility is a goal.
- [ ] Decide whether OpenGL compatibility is a goal.
- [ ] Decide whether OpenCL or compute compatibility is a goal.
- [ ] Define instance and device enumeration.
- [ ] Define physical-device properties.
- [ ] Define queues and queue families.
- [ ] Define command buffers.
- [ ] Define memory heaps and memory types.
- [ ] Define buffer objects.
- [ ] Define image objects.
- [ ] Define image layouts.
- [ ] Define synchronization primitives.
- [ ] Define semaphores.
- [ ] Define fences.
- [ ] Define timeline synchronization.
- [ ] Define render passes or dynamic rendering model.
- [ ] Define pipelines.
- [ ] Define descriptors.
- [ ] Define shader modules.
- [ ] Define presentation surfaces.
- [ ] Define swapchains.
- [ ] Define presentation timing.
- [ ] Define error and device-lost semantics.
- [ ] Port or implement SPIR-V tools if Vulkan is targeted.
- [ ] Port or implement a shader compiler.
- [ ] Validate shaders before device submission.
- [ ] Cache compiled shaders with versioned keys.
- [ ] Isolate shader compiler crashes from the compositor.
- [ ] Implement software reference rendering for conformance comparison.
- [ ] Run API conformance tests before advertising compatibility.

## 062. Audio Controller, Codec, and Kernel Audio Core

### 062.1 Audio core

- [ ] Define audio device object.
- [ ] Define PCM stream object.
- [ ] Define playback and capture directions.
- [ ] Define sample format enumeration.
- [ ] Define channel layout enumeration.
- [ ] Define sample rate.
- [ ] Define period size.
- [ ] Define buffer size.
- [ ] Define hardware position reporting.
- [ ] Define underrun and overrun behavior.
- [ ] Define stream start, pause, drain, and stop.
- [ ] Define mixer-control object.
- [ ] Define jack-detection events.
- [ ] Define clock-domain identity.
- [ ] Define DMA buffer ownership.
- [ ] Define exclusive and shared access.
- [ ] Define kernel/user audio boundary.
- [ ] Collect xrun and latency statistics.

### 062.2 Intel High Definition Audio controller path

- [ ] Match HDA PCI class code.
- [ ] Map controller registers.
- [ ] Reset controller.
- [ ] Read controller capabilities.
- [ ] Read codec-presence state.
- [ ] Configure CORB.
- [ ] Configure RIRB.
- [ ] Configure unsolicited responses.
- [ ] Send codec verbs.
- [ ] Receive codec responses.
- [ ] Enumerate codecs.
- [ ] Enumerate function groups.
- [ ] Enumerate widgets.
- [ ] Parse pin complexes.
- [ ] Parse amplifier capabilities.
- [ ] Parse PCM capabilities.
- [ ] Build codec routing graph.
- [ ] Select output path.
- [ ] Select input path.
- [ ] Configure converters.
- [ ] Configure stream descriptors.
- [ ] Allocate BDL entries.
- [ ] Program DMA position buffer if supported.
- [ ] Handle stream interrupts.
- [ ] Handle codec wake and jack events.
- [ ] Implement volume and mute.
- [ ] Implement controller reset recovery.
- [ ] Test exact target codec before generalization.

### 062.3 Audio quality and safety

- [ ] Prevent full-scale output during initialization.
- [ ] Start muted and ramp volume safely.
- [ ] Prevent integer overflow in sample conversion.
- [ ] Prevent buffer disclosure between processes.
- [ ] Zero playback buffers before reuse.
- [ ] Validate capture permissions.
- [ ] Measure end-to-end latency.
- [ ] Measure clock drift.
- [ ] Detect underruns and overruns.
- [ ] Test suspend and resume.
- [ ] Test device removal if USB audio is supported.
- [ ] Test multiple sample rates.
- [ ] Test mono, stereo, and multichannel paths.

## 063. Network Device Framework

- [ ] Define network-interface object.
- [ ] Define link-layer address.
- [ ] Define MTU.
- [ ] Define interface flags.
- [ ] Define link state.
- [ ] Define transmit queue.
- [ ] Define receive queue.
- [ ] Define packet buffer object.
- [ ] Define packet headroom and tailroom.
- [ ] Define scatter-gather packet segments.
- [ ] Define checksum metadata.
- [ ] Define offload capability flags.
- [ ] Define VLAN metadata.
- [ ] Define receive hashing metadata.
- [ ] Define timestamp metadata.
- [ ] Define interface statistics.
- [ ] Define transmit completion.
- [ ] Define queue stop and wake.
- [ ] Define carrier on and off.
- [ ] Define device reset.
- [ ] Define interface naming.
- [ ] Define hotplug events.
- [ ] Define namespace assignment if supported.
- [ ] Create loopback interface.
- [ ] Prevent packet data leakage from uninitialized memory.

## 064. Ethernet Driver and Link Layer

### 064.1 Target Ethernet driver

- [ ] Identify exact Ethernet controller and PHY.
- [ ] Acquire public programming documentation.
- [ ] Map BARs.
- [ ] Reset device.
- [ ] Read permanent MAC address.
- [ ] Allocate transmit descriptor rings.
- [ ] Allocate receive descriptor rings.
- [ ] Allocate packet buffers.
- [ ] Program DMA addresses.
- [ ] Configure interrupts.
- [ ] Enable receiver.
- [ ] Enable transmitter.
- [ ] Implement transmit queueing.
- [ ] Implement receive polling or interrupts.
- [ ] Replenish receive buffers.
- [ ] Handle multi-descriptor packets.
- [ ] Handle checksum offload only after software checksums are correct.
- [ ] Handle segmentation offload only after basic transmit is correct.
- [ ] Handle receive-side scaling only after single queue is stable.
- [ ] Handle link-state interrupt.
- [ ] Read PHY link status.
- [ ] Negotiate speed and duplex.
- [ ] Handle cable disconnect and reconnect.
- [ ] Implement device reset after hang.
- [ ] Stop DMA on shutdown.
- [ ] Test at multiple link speeds supported by hardware.

### 064.2 Ethernet framing

- [ ] Parse destination MAC address.
- [ ] Parse source MAC address.
- [ ] Parse EtherType or length.
- [ ] Validate minimum and maximum frame size.
- [ ] Handle padding.
- [ ] Handle FCS according to device behavior.
- [ ] Support broadcast.
- [ ] Support multicast filtering.
- [ ] Support promiscuous mode only with privilege.
- [ ] Support VLAN tags if required.
- [ ] Support stacked VLANs only if required.
- [ ] Drop malformed frames.
- [ ] Account drops by reason.

## 065. Wi-Fi Driver and 802.11 Stack

### 065.1 Hardware and regulatory prerequisites

- [ ] Identify exact Wi-Fi controller and transport.
- [ ] Acquire public programming documentation.
- [ ] Acquire legally redistributable firmware.
- [ ] Verify firmware hash and version.
- [ ] Identify supported bands.
- [ ] Identify supported channel widths.
- [ ] Identify supported PHY generations.
- [ ] Identify antenna configuration.
- [ ] Identify hardware crypto support.
- [ ] Identify scan offload support.
- [ ] Identify connection offload support.
- [ ] Identify power-save support.
- [ ] Implement PCIe, USB, or SDIO transport as applicable.
- [ ] Implement device reset.
- [ ] Implement firmware upload.
- [ ] Implement firmware command protocol.
- [ ] Implement firmware event protocol.
- [ ] Obtain regulatory-domain data from an authoritative source.
- [ ] Enforce country and channel restrictions.
- [ ] Enforce transmit power limits.
- [ ] Handle dynamic frequency selection only when fully implemented.
- [ ] Never transmit on unapproved channels.

### 065.2 802.11 MAC data structures

- [ ] Parse management frame headers.
- [ ] Parse control frame headers.
- [ ] Parse data frame headers.
- [ ] Handle address fields by distribution-system bits.
- [ ] Handle sequence and fragment numbers.
- [ ] Handle QoS control.
- [ ] Handle HT control if present.
- [ ] Parse information elements with bounds checks.
- [ ] Preserve unknown information elements.
- [ ] Parse SSID.
- [ ] Parse supported rates.
- [ ] Parse RSN information.
- [ ] Parse HT capabilities.
- [ ] Parse VHT capabilities.
- [ ] Parse HE capabilities.
- [ ] Parse EHT capabilities only if target hardware requires them.
- [ ] Parse channel-switch announcements.
- [ ] Parse country information.
- [ ] Fuzz management-frame parsing.

### 065.3 Scanning and association

- [ ] Implement passive scanning.
- [ ] Implement active scanning where regulatory rules permit.
- [ ] Build BSS cache.
- [ ] Expire stale BSS entries.
- [ ] Represent hidden SSIDs.
- [ ] Represent signal strength and noise.
- [ ] Represent channel and band.
- [ ] Select candidate network.
- [ ] Send authentication request.
- [ ] Handle authentication response.
- [ ] Send association request.
- [ ] Handle association response.
- [ ] Track association identifier.
- [ ] Handle deauthentication.
- [ ] Handle disassociation.
- [ ] Handle beacon loss.
- [ ] Handle roaming only after stable single-AP operation.
- [ ] Handle channel changes.
- [ ] Expose scan and connection state to network manager.

### 065.4 Wi-Fi security

- [ ] Implement 802.1X/EAPOL framing.
- [ ] Implement RSN negotiation.
- [ ] Implement WPA2-Personal four-way handshake.
- [ ] Implement WPA3-Personal SAE if targeted.
- [ ] Implement pairwise key derivation.
- [ ] Implement group key handshake.
- [ ] Implement replay counters.
- [ ] Implement nonce generation from a secure RNG.
- [ ] Implement CCMP-128 if software crypto is required.
- [ ] Implement GCMP only if required and correctly specified.
- [ ] Validate message integrity codes.
- [ ] Install pairwise keys atomically.
- [ ] Install group keys atomically.
- [ ] Prevent key reinstallation vulnerabilities.
- [ ] Handle protected management frames if required.
- [ ] Implement enterprise EAP methods only with a secure credential framework.
- [ ] Keep passphrases and derived keys out of logs.
- [ ] Zero key material after use.
- [ ] Test against hostile access-point behavior.

### 065.5 802.11 data path

- [ ] Encapsulate Ethernet or native IP into 802.11 data frames.
- [ ] Decapsulate received data frames.
- [ ] Handle QoS traffic identifiers.
- [ ] Handle sequence tracking.
- [ ] Handle duplicate suppression.
- [ ] Handle fragmentation only if required.
- [ ] Handle aggregation only after basic frames work.
- [ ] Handle block acknowledgements only after negotiated correctly.
- [ ] Handle rate control or firmware-reported rate selection.
- [ ] Handle power-save queues.
- [ ] Handle multicast and broadcast delivery.
- [ ] Collect per-station statistics.
- [ ] Collect retry and loss statistics.

## 066. Bluetooth Controller and Protocol Stack

### 066.1 HCI transport and controller

- [ ] Identify exact Bluetooth controller and transport.
- [ ] Load required firmware or patch RAM.
- [ ] Implement USB HCI transport if applicable.
- [ ] Implement UART HCI transport if applicable.
- [ ] Implement HCI command packets.
- [ ] Implement HCI event packets.
- [ ] Implement ACL data packets.
- [ ] Implement ISO data packets only if LE Audio is targeted.
- [ ] Track command credits.
- [ ] Track ACL buffer credits.
- [ ] Reset controller.
- [ ] Read local version.
- [ ] Read supported commands.
- [ ] Read supported features.
- [ ] Read buffer sizes.
- [ ] Set event masks.
- [ ] Configure random or public address.
- [ ] Handle hardware errors.
- [ ] Handle controller disconnect and reset.

### 066.2 Bluetooth host protocols

- [ ] Implement L2CAP signaling.
- [ ] Implement L2CAP basic channels.
- [ ] Implement LE credit-based channels when required.
- [ ] Implement SDP for classic profiles if targeted.
- [ ] Implement ATT.
- [ ] Implement GATT client.
- [ ] Implement GATT server if targeted.
- [ ] Implement SMP pairing.
- [ ] Implement key distribution.
- [ ] Implement bonding database.
- [ ] Implement privacy addresses if targeted.
- [ ] Implement GAP discovery.
- [ ] Implement GAP connection procedures.
- [ ] Implement RFCOMM if serial profiles are targeted.
- [ ] Implement AVDTP and A2DP if classic audio is targeted.
- [ ] Implement AVRCP if media control is targeted.
- [ ] Implement HID over GATT for keyboards and mice.
- [ ] Implement HID classic profile if required.
- [ ] Implement PAN only if networking profile is required.
- [ ] Validate every protocol length and channel identifier.
- [ ] Fuzz protocol parsers.

### 066.3 Bluetooth security and user experience

- [ ] Define discoverable mode timeout.
- [ ] Define connectable mode policy.
- [ ] Require user confirmation for pairing where appropriate.
- [ ] Support numeric comparison.
- [ ] Support passkey entry.
- [ ] Support just-works only with explicit risk policy.
- [ ] Store long-term keys encrypted.
- [ ] Allow bond removal.
- [ ] Display device identity and address.
- [ ] Handle address randomization.
- [ ] Restrict sensitive profile access.
- [ ] Protect input devices from unauthorized reconnection.
- [ ] Protect audio devices from silent hijacking.
- [ ] Log security events without logging secrets.

## 067. Packet Buffering, Routing, and Network Stack Core

- [ ] Define packet allocation pools.
- [ ] Define headroom requirements.
- [ ] Define tailroom requirements.
- [ ] Define cloning semantics.
- [ ] Define reference counting.
- [ ] Define linearization.
- [ ] Define scatter-gather traversal.
- [ ] Define checksum calculation helpers.
- [ ] Define protocol demultiplexing.
- [ ] Define ingress hook chain.
- [ ] Define egress hook chain.
- [ ] Define routing lookup.
- [ ] Define neighbor lookup.
- [ ] Define fragmentation policy.
- [ ] Define reassembly queues.
- [ ] Set bounded memory for reassembly.
- [ ] Set timeouts for reassembly.
- [ ] Prevent overlapping-fragment attacks.
- [ ] Define loopback path.
- [ ] Define interface-local addresses.
- [ ] Define forwarding policy.
- [ ] Disable forwarding by default on desktop builds.
- [ ] Account packets and bytes by layer.
- [ ] Drop malformed packets with reason codes.
- [ ] Fuzz packet parsers.

## 068. ARP, IPv4, and ICMPv4

### 068.1 ARP

- [ ] Parse ARP header.
- [ ] Validate hardware and protocol types.
- [ ] Validate address lengths.
- [ ] Handle ARP requests.
- [ ] Handle ARP replies.
- [ ] Create neighbor-cache entries.
- [ ] Define incomplete, reachable, stale, and failed states.
- [ ] Send bounded probes.
- [ ] Expire entries.
- [ ] Prevent untrusted overwrite of permanent entries.
- [ ] Apply anti-spoofing policy where appropriate.
- [ ] Handle gratuitous ARP.
- [ ] Detect address conflicts.

### 068.2 IPv4

- [ ] Parse IPv4 header.
- [ ] Validate version.
- [ ] Validate header length.
- [ ] Validate total length.
- [ ] Validate header checksum.
- [ ] Handle options safely or reject unsupported options.
- [ ] Handle local delivery.
- [ ] Handle forwarding only when enabled.
- [ ] Select source address.
- [ ] Perform route lookup.
- [ ] Apply TTL decrement on forwarding.
- [ ] Generate time-exceeded errors where required.
- [ ] Implement fragmentation for locally generated packets only if needed.
- [ ] Implement reassembly for received fragments.
- [ ] Implement path MTU discovery.
- [ ] Maintain route table.
- [ ] Support connected routes.
- [ ] Support default route.
- [ ] Support static routes.
- [ ] Support DHCP-installed routes.
- [ ] Reject martian and invalid source addresses according to policy.

### 068.3 ICMPv4

- [ ] Parse ICMPv4 messages.
- [ ] Validate checksum.
- [ ] Handle echo request.
- [ ] Generate echo reply.
- [ ] Handle destination unreachable.
- [ ] Handle fragmentation needed.
- [ ] Handle time exceeded.
- [ ] Handle parameter problem.
- [ ] Rate-limit error generation.
- [ ] Do not generate errors in response to prohibited packet classes.
- [ ] Deliver relevant errors to transport sockets.
- [ ] Support diagnostic ping utility.

## 069. IPv6, Neighbor Discovery, and ICMPv6

### 069.1 IPv6 core

- [ ] Parse IPv6 base header.
- [ ] Validate payload length.
- [ ] Process extension headers with strict bounds.
- [ ] Limit extension-header chain length.
- [ ] Handle hop-by-hop options under policy.
- [ ] Handle destination options under policy.
- [ ] Handle routing headers safely.
- [ ] Handle fragment header.
- [ ] Reject deprecated or unsafe routing forms.
- [ ] Perform local delivery.
- [ ] Perform route lookup.
- [ ] Select source address.
- [ ] Implement path MTU discovery.
- [ ] Implement reassembly.
- [ ] Do not fragment in routers.
- [ ] Generate fragments only at source when required.
- [ ] Support link-local addresses.
- [ ] Support global unicast addresses.
- [ ] Support multicast addresses.
- [ ] Support loopback.
- [ ] Maintain IPv6 route table.

### 069.2 Neighbor Discovery and SLAAC

- [ ] Handle router solicitation.
- [ ] Handle router advertisement.
- [ ] Validate hop limit and source requirements.
- [ ] Parse prefix information.
- [ ] Parse MTU option.
- [ ] Parse source link-layer option.
- [ ] Parse route information if supported.
- [ ] Create tentative addresses.
- [ ] Perform duplicate-address detection.
- [ ] Generate stable interface identifiers according to privacy policy.
- [ ] Generate temporary privacy addresses if selected.
- [ ] Track preferred and valid lifetimes.
- [ ] Deprecate expired addresses.
- [ ] Handle neighbor solicitation.
- [ ] Handle neighbor advertisement.
- [ ] Maintain neighbor-unreachability states.
- [ ] Perform reachability probes.
- [ ] Handle redirects only under strict validation.

### 069.3 ICMPv6

- [ ] Validate ICMPv6 checksum.
- [ ] Handle echo request and reply.
- [ ] Handle destination unreachable.
- [ ] Handle packet too big.
- [ ] Handle time exceeded.
- [ ] Handle parameter problem.
- [ ] Deliver errors to transport sockets.
- [ ] Rate-limit errors.
- [ ] Support multicast-listener discovery only if multicast management requires it.

## 070. UDP

- [ ] Define UDP socket state.
- [ ] Bind local address and port.
- [ ] Allocate ephemeral ports.
- [ ] Connect default peer.
- [ ] Send datagram.
- [ ] Receive datagram.
- [ ] Preserve datagram boundaries.
- [ ] Validate UDP length.
- [ ] Validate checksum.
- [ ] Require checksum for IPv6.
- [ ] Support optional zero checksum only where standards allow.
- [ ] Deliver ICMP errors.
- [ ] Support broadcast with privilege or socket option.
- [ ] Support multicast membership.
- [ ] Support nonblocking I/O.
- [ ] Support poll readiness.
- [ ] Support receive queue limits.
- [ ] Report truncation.
- [ ] Handle port unreachable generation.
- [ ] Fuzz socket option handling.

## 071. TCP

### 071.1 TCP state and segments

- [ ] Implement all required TCP connection states.
- [ ] Parse TCP header.
- [ ] Validate data offset.
- [ ] Validate checksum.
- [ ] Parse options with bounds checks.
- [ ] Support maximum segment size option.
- [ ] Support window scale option.
- [ ] Support timestamps if selected.
- [ ] Support selective acknowledgements.
- [ ] Generate initial sequence numbers from a secure construction.
- [ ] Handle SYN.
- [ ] Handle SYN-ACK.
- [ ] Handle ACK.
- [ ] Handle FIN.
- [ ] Handle RST.
- [ ] Handle simultaneous open if desired.
- [ ] Handle half-close.
- [ ] Handle TIME-WAIT.
- [ ] Handle keepalive only as an option.

### 071.2 Reliability and flow control

- [ ] Maintain send sequence variables.
- [ ] Maintain receive sequence variables.
- [ ] Maintain send window.
- [ ] Maintain receive window.
- [ ] Queue unacknowledged data.
- [ ] Queue out-of-order receive data.
- [ ] Generate acknowledgements.
- [ ] Implement delayed acknowledgements.
- [ ] Implement retransmission timer.
- [ ] Estimate round-trip time.
- [ ] Apply retransmission backoff.
- [ ] Handle duplicate acknowledgements.
- [ ] Implement fast retransmit.
- [ ] Implement selective-acknowledgement recovery.
- [ ] Handle zero windows.
- [ ] Implement persist timer.
- [ ] Handle urgent data only if compatibility requires it.
- [ ] Prevent sequence-number arithmetic bugs.
- [ ] Bound memory per connection.

### 071.3 Congestion control

- [ ] Implement a standards-compliant initial congestion-control algorithm.
- [ ] Maintain congestion window.
- [ ] Maintain slow-start threshold.
- [ ] Implement slow start.
- [ ] Implement congestion avoidance.
- [ ] Implement loss response.
- [ ] Implement recovery.
- [ ] Implement pacing only after correctness.
- [ ] Allow pluggable congestion-control algorithms later.
- [ ] Measure algorithm behavior under loss and reordering.
- [ ] Prevent PDC network policy from violating congestion-control safety.

### 071.4 TCP sockets

- [ ] Implement listen.
- [ ] Implement accept.
- [ ] Implement active connect.
- [ ] Implement backlog queues.
- [ ] Protect against SYN-flood resource exhaustion.
- [ ] Implement send buffer.
- [ ] Implement receive buffer.
- [ ] Implement Nagle option.
- [ ] Implement corking only if needed.
- [ ] Implement linger semantics.
- [ ] Implement nonblocking connect.
- [ ] Implement shutdown.
- [ ] Deliver asynchronous errors.
- [ ] Expose connection statistics.
- [ ] Test high connection counts.
- [ ] Test loss, reordering, duplication, and delay.

## 072. Socket API and Network Names

- [ ] Define address-family constants.
- [ ] Define socket types.
- [ ] Define protocol identifiers.
- [ ] Define socket address structures.
- [ ] Version extensible structures.
- [ ] Implement socket creation.
- [ ] Implement bind.
- [ ] Implement connect.
- [ ] Implement listen.
- [ ] Implement accept.
- [ ] Implement send.
- [ ] Implement receive.
- [ ] Implement sendto and recvfrom.
- [ ] Implement sendmsg and recvmsg.
- [ ] Implement ancillary data.
- [ ] Implement socket options.
- [ ] Implement get local name.
- [ ] Implement get peer name.
- [ ] Implement shutdown.
- [ ] Implement close.
- [ ] Implement nonblocking mode.
- [ ] Implement readiness polling.
- [ ] Implement per-socket timeouts.
- [ ] Implement interface binding.
- [ ] Implement multicast joins.
- [ ] Implement privilege checks.
- [ ] Fuzz all socket APIs.

## 073. Network Configuration and Core Services

### 073.1 DHCPv4

- [ ] Construct DHCPDISCOVER.
- [ ] Parse DHCPOFFER.
- [ ] Construct DHCPREQUEST.
- [ ] Parse DHCPACK and DHCPNAK.
- [ ] Validate transaction identifier.
- [ ] Validate server identifier.
- [ ] Parse subnet mask.
- [ ] Parse routers.
- [ ] Parse DNS servers.
- [ ] Parse lease time.
- [ ] Parse renewal and rebinding times.
- [ ] Parse domain search list safely.
- [ ] Parse classless static routes safely.
- [ ] Implement INIT, SELECTING, REQUESTING, BOUND, RENEWING, REBINDING, and INIT-REBOOT states.
- [ ] Persist leases where useful.
- [ ] Handle address conflict detection.
- [ ] Release lease on orderly shutdown only under policy.
- [ ] Fuzz option parsing.

### 073.2 DHCPv6 and router configuration

- [ ] Decide whether stateless DHCPv6 is required.
- [ ] Decide whether stateful DHCPv6 is required.
- [ ] Generate DUID.
- [ ] Implement solicit, advertise, request, reply, renew, rebind, and release when targeted.
- [ ] Parse DNS and domain options.
- [ ] Coordinate with router advertisements.
- [ ] Validate transaction identifiers.
- [ ] Fuzz option parsing.

### 073.3 DNS resolver

- [ ] Encode DNS query names.
- [ ] Decode compressed DNS names with loop detection.
- [ ] Validate message header.
- [ ] Validate section counts.
- [ ] Parse A records.
- [ ] Parse AAAA records.
- [ ] Parse CNAME records.
- [ ] Parse PTR records.
- [ ] Parse MX and SRV only if needed.
- [ ] Parse TXT only if needed.
- [ ] Handle truncated UDP responses.
- [ ] Retry over TCP.
- [ ] Randomize query identifiers and source ports.
- [ ] Validate response question and source.
- [ ] Implement search domains.
- [ ] Implement timeout and server rotation.
- [ ] Cache positive responses.
- [ ] Cache negative responses.
- [ ] Respect TTLs.
- [ ] Bound cache memory.
- [ ] Support `/etc/hosts`-equivalent static names.
- [ ] Implement DNSSEC validation only as a complete, tested feature.
- [ ] Fuzz compression pointers and record lengths.

### 073.4 Time synchronization

- [ ] Implement NTP client or port an audited implementation.
- [ ] Use multiple time sources.
- [ ] Validate server responses.
- [ ] Reject implausible offsets.
- [ ] Estimate delay and dispersion.
- [ ] Step clock only under startup policy.
- [ ] Slew clock during normal operation.
- [ ] Track synchronization status.
- [ ] Handle leap indicators.
- [ ] Persist drift estimate.
- [ ] Implement Network Time Security only if a complete authenticated design is available.
- [ ] Prevent unauthenticated network time from silently controlling security-critical validity without policy.

### 073.5 Network manager

- [ ] Enumerate interfaces.
- [ ] Track link state.
- [ ] Track addresses.
- [ ] Track routes.
- [ ] Track DNS configuration.
- [ ] Manage Ethernet profiles.
- [ ] Manage Wi-Fi profiles.
- [ ] Store credentials securely.
- [ ] Select preferred connection.
- [ ] Handle captive networks under user control.
- [ ] Handle metered-network policy.
- [ ] Handle offline mode.
- [ ] Expose status to desktop UI.
- [ ] Expose a command-line interface.
- [ ] Emit structured state-change events.
- [ ] Avoid restarting interfaces during unrelated configuration changes.

## 074. Firewall, Packet Filtering, NAT, and VPN Boundaries

- [ ] Define packet-filter hook points.
- [ ] Define rule representation.
- [ ] Define rule ordering.
- [ ] Define default inbound policy.
- [ ] Define default outbound policy.
- [ ] Define loopback policy.
- [ ] Define established-flow tracking if stateful filtering is used.
- [ ] Define fragment handling.
- [ ] Define ICMP and ICMPv6 policy.
- [ ] Define logging and rate limits.
- [ ] Define per-application policy only after identity binding is sound.
- [ ] Implement rule validation.
- [ ] Implement atomic rule replacement.
- [ ] Prevent unprivileged rule changes.
- [ ] Expose counters.
- [ ] Fuzz rule parser.
- [ ] Implement NAT only if routing use cases require it.
- [ ] Implement port forwarding only if explicitly configured.
- [ ] Implement VPN tunnel interface abstraction.
- [ ] Port or implement WireGuard-like cryptographic VPN only after crypto review.
- [ ] Never invent unreviewed cryptography for VPN use.

## 075. TLS, Certificates, and Secure Network Client Foundation

- [ ] Choose an audited TLS library to port or define a complete custom implementation plan.
- [ ] Support TLS 1.3 before advertising secure web compatibility.
- [ ] Implement cryptographic algorithm negotiation.
- [ ] Implement secure key exchange.
- [ ] Implement transcript hashing.
- [ ] Implement certificate parsing.
- [ ] Implement X.509 path validation.
- [ ] Implement hostname verification.
- [ ] Implement signature verification.
- [ ] Implement validity-time checks.
- [ ] Implement revocation policy.
- [ ] Implement root trust store.
- [ ] Define root-store update process.
- [ ] Isolate ASN.1 and certificate parsers.
- [ ] Fuzz all certificate and handshake parsers.
- [ ] Protect private keys in memory.
- [ ] Prevent downgrade to obsolete protocols.
- [ ] Disable insecure cipher suites.
- [ ] Implement secure session resumption.
- [ ] Implement random generation through kernel CSPRNG.
- [ ] Expose precise validation errors without leaking secrets.
- [ ] Create interoperability tests against independent servers.

## 076. Virtual Filesystem Core

### 076.1 VFS objects

- [ ] Define filesystem type.
- [ ] Define superblock or mounted-volume object.
- [ ] Define inode or vnode object.
- [ ] Define directory-entry object.
- [ ] Define open-file-description object.
- [ ] Define file-descriptor reference.
- [ ] Define mount object.
- [ ] Define path object.
- [ ] Define filesystem operations.
- [ ] Define inode operations.
- [ ] Define file operations.
- [ ] Define directory iteration operations.
- [ ] Define address-space or page-cache operations.
- [ ] Define extended-attribute operations.
- [ ] Define permission hooks.
- [ ] Define notification hooks.
- [ ] Define object lifetime and reference counts.
- [ ] Prevent use-after-unmount.
- [ ] Prevent cyclic mount references.

### 076.2 Path resolution

- [ ] Define path separator.
- [ ] Define root path.
- [ ] Define current working directory.
- [ ] Handle repeated separators.
- [ ] Handle `.` components.
- [ ] Handle `..` components.
- [ ] Handle mount crossings.
- [ ] Handle chroot or namespace roots if supported.
- [ ] Resolve symbolic links.
- [ ] Limit symbolic-link depth.
- [ ] Prevent path-length overflow.
- [ ] Define maximum component length.
- [ ] Define maximum path length.
- [ ] Define case sensitivity.
- [ ] Define Unicode normalization policy.
- [ ] Define invalid-byte policy.
- [ ] Handle trailing slash semantics.
- [ ] Handle final-component non-follow options.
- [ ] Prevent races with concurrent rename and unmount.
- [ ] Implement lookup caching.
- [ ] Invalidate cache correctly.
- [ ] Fuzz path resolution.

### 076.3 Core file operations

- [ ] Implement open.
- [ ] Implement create.
- [ ] Implement close.
- [ ] Implement read.
- [ ] Implement write.
- [ ] Implement positioned read.
- [ ] Implement positioned write.
- [ ] Implement seek.
- [ ] Implement truncate.
- [ ] Implement allocate or preallocate if supported.
- [ ] Implement metadata query.
- [ ] Implement metadata update.
- [ ] Implement create directory.
- [ ] Implement remove directory.
- [ ] Implement link.
- [ ] Implement unlink.
- [ ] Implement symbolic link.
- [ ] Implement rename.
- [ ] Implement atomic rename replacement.
- [ ] Implement directory iteration.
- [ ] Implement filesystem synchronization.
- [ ] Implement file synchronization.
- [ ] Implement data-only synchronization.
- [ ] Implement advisory locking.
- [ ] Implement mandatory locking only if explicitly designed.
- [ ] Implement memory mapping.
- [ ] Implement pollability for special files.
- [ ] Define append atomicity.
- [ ] Define short read and short write semantics.
- [ ] Define interrupted operation semantics.

### 076.4 Permissions and metadata

- [ ] Define owner user ID.
- [ ] Define owner group ID.
- [ ] Define mode bits.
- [ ] Define timestamps.
- [ ] Define timestamp precision.
- [ ] Define creation time if supported.
- [ ] Define change time.
- [ ] Define modification time.
- [ ] Define access time policy.
- [ ] Define inode generation number.
- [ ] Define device ID.
- [ ] Define file type.
- [ ] Define link count.
- [ ] Define extended attributes.
- [ ] Define ACL storage.
- [ ] Define security labels.
- [ ] Apply umask on creation.
- [ ] Check search permission on every traversed directory.
- [ ] Check final-object access.
- [ ] Apply sticky-directory semantics if POSIX-like.
- [ ] Handle set-user-ID and set-group-ID bits according to policy.
- [ ] Audit privileged metadata changes.

## 077. Page Cache, Writeback, and File Mapping

- [ ] Define page-cache key.
- [ ] Lookup cached page.
- [ ] Allocate cache page.
- [ ] Lock cache page.
- [ ] Mark page uptodate.
- [ ] Mark page dirty.
- [ ] Start read I/O.
- [ ] Complete read I/O.
- [ ] Start writeback.
- [ ] Complete writeback.
- [ ] Handle I/O errors persistently.
- [ ] Track dirty memory.
- [ ] Set dirty-memory limits.
- [ ] Throttle writers.
- [ ] Run background writeback.
- [ ] Order metadata and data according to filesystem guarantees.
- [ ] Invalidate cache on truncate.
- [ ] Invalidate cache on direct writes.
- [ ] Coordinate mmap and read/write paths.
- [ ] Handle write fault on shared mappings.
- [ ] Handle private copy-on-write mappings.
- [ ] Implement read-ahead.
- [ ] Implement write clustering.
- [ ] Avoid data exposure from partially initialized pages.
- [ ] Handle storage removal with dirty pages.
- [ ] Expose writeback and cache statistics.
- [ ] Test power loss at every ordering point.

## 078. Pseudo Filesystems and Initial RAM Filesystem

### 078.1 Initramfs

- [ ] Choose initramfs archive format.
- [ ] Implement archive parser.
- [ ] Validate path names.
- [ ] Prevent path traversal.
- [ ] Validate file sizes.
- [ ] Validate alignment.
- [ ] Support regular files.
- [ ] Support directories.
- [ ] Support symbolic links.
- [ ] Support device-node metadata only under trusted policy.
- [ ] Support permissions and ownership.
- [ ] Load first user-space executable.
- [ ] Mount initramfs as initial root.
- [ ] Free archive memory only after extraction or preserve compressed backing intentionally.
- [ ] Verify initramfs signature before use.
- [ ] Fuzz archive parser.

### 078.2 Memory-backed filesystems

- [ ] Implement ramfs-like filesystem.
- [ ] Implement tmpfs-like size limits.
- [ ] Account memory to mount or resource group.
- [ ] Support sparse files.
- [ ] Support swapping only after swap is complete.
- [ ] Support permissions.
- [ ] Support directories and links.
- [ ] Support memory mapping.
- [ ] Prevent unbounded growth.
- [ ] Use for temporary directories.
- [ ] Use for runtime state.
- [ ] Use for shared-memory filesystem if selected.

### 078.3 Device and system information filesystems

- [ ] Implement dynamic device filesystem or equivalent device namespace.
- [ ] Create and remove device nodes on hotplug.
- [ ] Expose process information through a structured API or proc-like filesystem.
- [ ] Expose kernel and device properties through a structured API or sys-like filesystem.
- [ ] Define stable versus unstable fields.
- [ ] Restrict sensitive addresses and identifiers.
- [ ] Avoid text parsing as the only control plane for security-critical actions.
- [ ] Provide binary or structured interfaces where appropriate.
- [ ] Test concurrent enumeration and removal.

## 079. FAT32 Support for EFI System Partition

- [ ] Parse BIOS parameter block.
- [ ] Validate bytes per sector.
- [ ] Validate sectors per cluster.
- [ ] Validate reserved sector count.
- [ ] Validate FAT count.
- [ ] Validate total sectors.
- [ ] Validate FAT size.
- [ ] Validate root cluster.
- [ ] Validate FSInfo signatures.
- [ ] Read FAT entries.
- [ ] Detect bad clusters.
- [ ] Detect end-of-chain markers.
- [ ] Follow cluster chains with loop detection.
- [ ] Read short directory entries.
- [ ] Read long filename entries.
- [ ] Validate long filename checksums.
- [ ] Decode UTF-16 filenames.
- [ ] Handle deleted and free entries.
- [ ] Read files.
- [ ] Read directories.
- [ ] Implement read-only mount first.
- [ ] Implement writes only if boot-update design requires them.
- [ ] Allocate clusters safely.
- [ ] Update all FAT copies according to policy.
- [ ] Update FSInfo hints conservatively.
- [ ] Flush metadata in crash-aware order.
- [ ] Never use ESP as general mutable user storage.
- [ ] Fuzz malformed FAT images.

## 080. Production Root Filesystem or PooleFS

### 080.1 On-disk format

- [ ] Assign filesystem type identifier.
- [ ] Assign on-disk format version.
- [ ] Define byte order.
- [ ] Define block size.
- [ ] Define minimum and maximum volume size.
- [ ] Define superblock locations.
- [ ] Define backup superblocks if used.
- [ ] Define volume UUID.
- [ ] Define feature flags.
- [ ] Define compatible feature flags.
- [ ] Define read-only-compatible feature flags.
- [ ] Define incompatible feature flags.
- [ ] Define checksum algorithm.
- [ ] Define superblock checksum.
- [ ] Define allocation metadata.
- [ ] Define inode format.
- [ ] Define directory format.
- [ ] Define extent or block-pointer format.
- [ ] Define free-space format.
- [ ] Define journal or copy-on-write root format.
- [ ] Define snapshot metadata if supported.
- [ ] Define quota metadata if supported.
- [ ] Define encryption metadata if supported.
- [ ] Define compression metadata if supported.
- [ ] Define error-state flags.
- [ ] Document every field and alignment requirement.
- [ ] Create a format parser independent from kernel implementation.

### 080.2 Allocation and free space

- [ ] Allocate data blocks.
- [ ] Allocate metadata blocks.
- [ ] Free blocks.
- [ ] Detect double allocation.
- [ ] Detect double free.
- [ ] Track extents.
- [ ] Handle fragmentation.
- [ ] Preallocate sequential files.
- [ ] Reserve emergency metadata space.
- [ ] Reserve journal space.
- [ ] Handle full filesystem.
- [ ] Handle metadata-full condition separately from data-full condition.
- [ ] Provide free-space query.
- [ ] Provide discard/TRIM integration.
- [ ] Avoid exposing stale freed data to new owners.
- [ ] Zero or securely initialize allocated blocks according to policy.
- [ ] Verify allocator consistency offline.

### 080.3 Files and directories

- [ ] Create inode.
- [ ] Delete inode.
- [ ] Increment and decrement link count.
- [ ] Store inline small data only if designed.
- [ ] Store direct extents.
- [ ] Store indirect extent trees.
- [ ] Grow files.
- [ ] Shrink files.
- [ ] Punch holes if supported.
- [ ] Create directory entries.
- [ ] Remove directory entries.
- [ ] Lookup directory entries.
- [ ] Iterate directory entries.
- [ ] Handle hash collisions if hashed directories are used.
- [ ] Support atomic rename.
- [ ] Support hard links.
- [ ] Support symbolic links.
- [ ] Support sparse files.
- [ ] Support large files.
- [ ] Support extended attributes.
- [ ] Support ACLs.
- [ ] Support security labels.

### 080.4 Crash consistency

- [ ] Choose journaling, copy-on-write, log-structured, or another consistency model.
- [ ] Define transaction boundaries.
- [ ] Define ordering guarantees.
- [ ] Define fsync guarantees.
- [ ] Define fdatasync guarantees.
- [ ] Define rename durability guarantees.
- [ ] Define directory fsync semantics.
- [ ] Define write-cache assumptions.
- [ ] Issue flush at required boundaries.
- [ ] Use FUA where required and supported.
- [ ] Handle torn sector writes.
- [ ] Checksum critical metadata.
- [ ] Replay journal after unclean shutdown.
- [ ] Detect incomplete transactions.
- [ ] Roll back or roll forward deterministically.
- [ ] Make replay idempotent.
- [ ] Prevent replay from reading outside volume bounds.
- [ ] Power-cut test every metadata operation.
- [ ] Power-cut test updates and rollback.

### 080.5 Integrity, repair, and maintenance

- [ ] Create read-only filesystem checker.
- [ ] Create repair-capable filesystem checker.
- [ ] Validate superblocks.
- [ ] Validate allocation maps.
- [ ] Validate inode references.
- [ ] Validate link counts.
- [ ] Validate directory structure.
- [ ] Validate extent trees.
- [ ] Validate checksums.
- [ ] Detect orphaned inodes.
- [ ] Detect lost blocks.
- [ ] Recover files to a lost-and-found area only under explicit repair policy.
- [ ] Create online scrub if checksums exist.
- [ ] Create offline backup and restore tools.
- [ ] Create image dump tool.
- [ ] Create metadata debugger.
- [ ] Create format migration tool.
- [ ] Never auto-repair ambiguous corruption without preserving evidence.
- [ ] Test repair tools on generated corruption corpus.

## 081. Storage Encryption, Key Management, and Swap

### 081.1 Block or filesystem encryption

- [ ] Choose block-level, filesystem-level, or per-file encryption model.
- [ ] Choose authenticated versus unauthenticated storage mode.
- [ ] Use standardized reviewed cryptographic primitives.
- [ ] Define volume header format.
- [ ] Define keyslots.
- [ ] Define key derivation from passphrases.
- [ ] Define hardware-backed key unsealing option.
- [ ] Define recovery key format.
- [ ] Define key rotation.
- [ ] Define key revocation.
- [ ] Define metadata authentication.
- [ ] Define sector or block tweak construction.
- [ ] Define nonce uniqueness rules.
- [ ] Define integrity tag storage.
- [ ] Define replay protection if required.
- [ ] Prevent plaintext key paging.
- [ ] Zero keys on lock, shutdown, and error paths.
- [ ] Prevent keys from crash dumps.
- [ ] Rate-limit passphrase attempts.
- [ ] Support read-only recovery unlock.
- [ ] Create backup and restore procedure for encryption metadata.
- [ ] Fuzz volume-header parser.
- [ ] Obtain independent cryptographic review before production use.

### 081.2 Swap and paging store

- [ ] Decide whether swap is required.
- [ ] Define swap area format.
- [ ] Define swap slot allocation.
- [ ] Define swap metadata persistence policy.
- [ ] Implement page-out selection.
- [ ] Implement page-out I/O.
- [ ] Implement page-in fault resolution.
- [ ] Handle swap I/O errors.
- [ ] Account swap per process and system.
- [ ] Encrypt swap by default when enabled.
- [ ] Use ephemeral swap encryption keys where appropriate.
- [ ] Prevent kernel secrets from being swapped unless policy allows.
- [ ] Prevent pinned DMA pages from being swapped.
- [ ] Integrate tmpfs with swap only after correctness.
- [ ] Handle swap-device removal safely.
- [ ] Expose swap pressure statistics.
- [ ] Test under memory exhaustion and I/O failure.

## 082. Executable Format and Program Loader

### 082.1 ELF validation

- [ ] Validate ELF magic.
- [ ] Validate 64-bit class.
- [ ] Validate little-endian encoding.
- [ ] Validate ELF version.
- [ ] Validate x86-64 machine type.
- [ ] Validate executable or shared-object type.
- [ ] Validate header sizes.
- [ ] Validate program-header offset and count.
- [ ] Validate section-header fields only when consumed.
- [ ] Validate all file offsets and sizes.
- [ ] Prevent integer overflow.
- [ ] Reject overlapping file regions when unsafe.
- [ ] Reject unsupported segment types according to policy.
- [ ] Reject executable stack unless explicitly permitted.
- [ ] Reject writable and executable segments by default.

### 082.2 Process image construction

- [ ] Create new address space.
- [ ] Map PT_LOAD segments.
- [ ] Apply file permissions to mappings.
- [ ] Zero memory beyond file data.
- [ ] Apply load bias for position-independent executables.
- [ ] Map dynamic linker when required.
- [ ] Map interpreter specified by PT_INTERP.
- [ ] Map thread-local storage template.
- [ ] Map program header information for runtime access.
- [ ] Map user stack.
- [ ] Randomize stack.
- [ ] Place argument strings.
- [ ] Place environment strings.
- [ ] Construct argument vector.
- [ ] Construct environment vector.
- [ ] Construct auxiliary vector.
- [ ] Provide page size.
- [ ] Provide entry point.
- [ ] Provide secure-execution flag.
- [ ] Provide random bytes.
- [ ] Provide executable path or handle.
- [ ] Provide system ABI version.
- [ ] Apply resource limits.
- [ ] Commit new image atomically.
- [ ] Preserve old image if loading fails.
- [ ] Close close-on-exec handles.
- [ ] Reset signal dispositions as defined.
- [ ] Reset thread state to one thread.

### 082.3 Static and dynamic relocations

- [ ] Support required x86-64 absolute relocations.
- [ ] Support required PC-relative relocations.
- [ ] Support relative relocations.
- [ ] Support global offset table.
- [ ] Support procedure linkage table if selected.
- [ ] Support copy relocations only if compatibility requires them.
- [ ] Support initial-exec and local-exec TLS relocations.
- [ ] Support dynamic TLS model only after base TLS is stable.
- [ ] Detect relocation overflow.
- [ ] Validate relocation targets lie in mapped objects.
- [ ] Protect relocation metadata from malformed binaries.
- [ ] Apply RELRO protections after relocation.
- [ ] Implement lazy binding only if security and complexity justify it.
- [ ] Prefer immediate binding for privileged programs.
- [ ] Fuzz relocation tables.

## 083. Dynamic Linker and Shared Library Runtime

- [ ] Define shared-object naming convention.
- [ ] Define soname semantics.
- [ ] Define library search order.
- [ ] Define trusted system library paths.
- [ ] Define per-application library paths.
- [ ] Ignore unsafe environment overrides for privileged executables.
- [ ] Load dependencies recursively.
- [ ] Detect dependency cycles.
- [ ] Map shared objects with ASLR.
- [ ] Resolve symbols.
- [ ] Implement symbol visibility.
- [ ] Implement weak symbols.
- [ ] Implement versioned symbols only if required.
- [ ] Apply relocations.
- [ ] Initialize TLS modules.
- [ ] Run constructors in dependency order.
- [ ] Run destructors in reverse order.
- [ ] Implement `dlopen`-like loading if targeted.
- [ ] Implement `dlsym`-like lookup if targeted.
- [ ] Implement `dlclose` semantics conservatively.
- [ ] Protect global offset tables after relocation.
- [ ] Provide audit diagnostics for missing symbols.
- [ ] Generate dependency inspection tool.
- [ ] Fuzz malformed dynamic sections.

## 084. C Runtime, Compiler Runtime, and Standard Library

### 084.1 Process startup and termination

- [ ] Implement user-space entry stub.
- [ ] Parse initial stack.
- [ ] Initialize thread-local storage.
- [ ] Initialize stack canary.
- [ ] Initialize libc global state.
- [ ] Run pre-initialization functions.
- [ ] Run constructors.
- [ ] Call program main.
- [ ] Run registered exit handlers.
- [ ] Flush standard I/O.
- [ ] Run destructors.
- [ ] Invoke process-exit system call.
- [ ] Implement immediate exit path.
- [ ] Implement abort path.
- [ ] Implement assertion failure path.

### 084.2 Fundamental C library

- [ ] Implement memory copy.
- [ ] Implement memory move.
- [ ] Implement memory set.
- [ ] Implement memory comparison.
- [ ] Implement string length.
- [ ] Implement bounded string operations.
- [ ] Implement string comparison.
- [ ] Implement string search.
- [ ] Implement tokenization with thread-safe variants.
- [ ] Implement numeric conversion.
- [ ] Implement character classification.
- [ ] Implement error string handling.
- [ ] Implement environment access.
- [ ] Implement process termination.
- [ ] Implement sorting.
- [ ] Implement binary search.
- [ ] Implement random API backed by explicit secure or nonsecure generators.
- [ ] Implement multibyte and wide-character primitives.
- [ ] Test every routine against independent conformance vectors.
- [ ] Optimize only after scalar reference correctness.

### 084.3 Memory allocation

- [ ] Implement malloc.
- [ ] Implement calloc with overflow checking.
- [ ] Implement realloc.
- [ ] Implement free.
- [ ] Implement aligned allocation.
- [ ] Implement allocation-size query only if ABI defines it.
- [ ] Handle zero-size allocation consistently.
- [ ] Handle large allocation through virtual-memory mappings.
- [ ] Handle small allocation through arenas or bins.
- [ ] Provide thread safety.
- [ ] Prevent integer overflow.
- [ ] Detect corruption in debug allocator.
- [ ] Support guard-page mode.
- [ ] Support leak-report mode.
- [ ] Avoid returning uninitialized cross-process data.
- [ ] Test fragmentation and multithreaded stress.

### 084.4 Standard I/O

- [ ] Define FILE object.
- [ ] Implement standard input, output, and error.
- [ ] Implement buffered read.
- [ ] Implement buffered write.
- [ ] Implement line buffering.
- [ ] Implement unbuffered mode.
- [ ] Implement flush.
- [ ] Implement seek and tell.
- [ ] Implement file open and reopen.
- [ ] Implement close.
- [ ] Implement character I/O.
- [ ] Implement line I/O.
- [ ] Implement block I/O.
- [ ] Implement formatted output.
- [ ] Implement formatted input only with strict bounds handling.
- [ ] Implement temporary files securely.
- [ ] Implement file locking for thread safety.
- [ ] Handle partial writes and interruptions.
- [ ] Fuzz format-string implementations.

### 084.5 Mathematics and floating point

- [ ] Implement required integer math helpers.
- [ ] Implement basic floating-point classification.
- [ ] Implement rounding functions.
- [ ] Implement transcendental functions or port a reviewed math library.
- [ ] Implement floating-point environment control.
- [ ] Define errno and exception behavior.
- [ ] Test edge cases, NaNs, infinities, subnormals, and signed zero.
- [ ] Validate accuracy targets.
- [ ] Avoid architecture-specific optimization without reference comparison.

### 084.6 Time, locale, and text

- [ ] Implement time types with year-2038-safe widths.
- [ ] Implement broken-down time conversion.
- [ ] Implement monotonic and realtime clock APIs.
- [ ] Implement sleep and timed wait APIs.
- [ ] Load IANA timezone database.
- [ ] Implement timezone conversion.
- [ ] Implement daylight-saving transitions.
- [ ] Implement locale object.
- [ ] Implement numeric formatting rules.
- [ ] Implement collation or clearly document limited support.
- [ ] Implement Unicode conversion.
- [ ] Implement UTF-8 validation.
- [ ] Implement UTF-16 conversion for UEFI and external formats.
- [ ] Implement normalization only if required by API.
- [ ] Implement locale-independent security comparisons.
- [ ] Version timezone and locale data.

## 085. Thread Library and User-Space Synchronization

- [ ] Define thread identifier.
- [ ] Implement thread creation.
- [ ] Implement thread exit.
- [ ] Implement join.
- [ ] Implement detach.
- [ ] Implement thread-local storage keys.
- [ ] Implement thread naming.
- [ ] Implement cancellation policy if supported.
- [ ] Implement mutex.
- [ ] Implement recursive mutex only if required.
- [ ] Implement error-checking mutex only if required.
- [ ] Implement read-write lock.
- [ ] Implement condition variable.
- [ ] Implement semaphore.
- [ ] Implement barrier.
- [ ] Implement once initialization.
- [ ] Implement spinlock only where appropriate.
- [ ] Implement robust mutex if targeted.
- [ ] Use futex-like kernel primitive for blocking.
- [ ] Handle process-shared synchronization.
- [ ] Define memory-ordering semantics.
- [ ] Test cancellation and signal interactions.
- [ ] Stress-test lost wakeups and destruction races.

## 086. POSIX and Application ABI Compatibility Matrix

- [ ] Create a complete POSIX.1-2024 interface inventory.
- [ ] Mark each interface implemented, partially implemented, planned, omitted, or incompatible.
- [ ] Create a shell and utilities inventory.
- [ ] Create a headers inventory.
- [ ] Create an errno inventory.
- [ ] Create a signal inventory.
- [ ] Create a filesystem-semantics inventory.
- [ ] Create a process-semantics inventory.
- [ ] Create a thread-semantics inventory.
- [ ] Create a socket-semantics inventory.
- [ ] Create a terminal-semantics inventory.
- [ ] Create a locale-semantics inventory.
- [ ] Create a realtime-extension inventory.
- [ ] Create an optional-feature inventory.
- [ ] Run open conformance suites where licensing permits.
- [ ] Write independent tests for PooleOS-specific deviations.
- [ ] Do not claim POSIX conformance without the applicable formal process.
- [ ] Publish source-level portability guidance.

## 087. Rust and Other Language Runtime Support

- [ ] Define the PooleOS Rust target specification.
- [ ] Define data layout.
- [ ] Define panic strategy.
- [ ] Define unwinding support or abort-only policy.
- [ ] Provide allocator hooks.
- [ ] Provide thread-local storage support.
- [ ] Provide atomic support.
- [ ] Provide stack-protector integration if applicable.
- [ ] Provide startup objects.
- [ ] Provide system-call bindings.
- [ ] Port or build `core`.
- [ ] Port or build `alloc`.
- [ ] Port `std` only after filesystem, threading, networking, time, and process APIs exist.
- [ ] Define C ABI interoperability.
- [ ] Define exception or panic boundary rules.
- [ ] Prevent unwinding across unsupported ABI boundaries.
- [ ] Create language-specific package metadata.
- [ ] Create debugger support.
- [ ] Create crash-symbolization support.
- [ ] Add support for C++, Zig, Go, or other languages only with explicit runtime plans.

## 088. Core User-Space Utilities

### 088.1 Essential boot and filesystem utilities

- [ ] Implement or port mount utility.
- [ ] Implement or port unmount utility.
- [ ] Implement or port filesystem check utility.
- [ ] Implement or port filesystem format utility.
- [ ] Implement or port block-device listing utility.
- [ ] Implement or port partition listing utility.
- [ ] Implement or port file copy utility.
- [ ] Implement or port file move utility.
- [ ] Implement or port file removal utility.
- [ ] Implement or port directory creation utility.
- [ ] Implement or port link utility.
- [ ] Implement or port file metadata utility.
- [ ] Implement or port disk usage utility.
- [ ] Implement or port free-space utility.
- [ ] Implement or port archive extraction utility.
- [ ] Implement or port checksum utility.
- [ ] Implement or port secure file comparison utility.

### 088.2 Process and system utilities

- [ ] Implement process listing.
- [ ] Implement process tree display.
- [ ] Implement process termination utility.
- [ ] Implement priority adjustment utility.
- [ ] Implement CPU affinity utility.
- [ ] Implement memory information utility.
- [ ] Implement uptime utility.
- [ ] Implement kernel message viewer.
- [ ] Implement hardware inventory utility.
- [ ] Implement PCI inventory utility.
- [ ] Implement USB inventory utility.
- [ ] Implement storage health utility.
- [ ] Implement network interface utility.
- [ ] Implement route utility.
- [ ] Implement socket listing utility.
- [ ] Implement system time utility.
- [ ] Implement user identity utility.
- [ ] Implement environment utility.
- [ ] Implement service-control utility.
- [ ] Implement reboot utility.
- [ ] Implement shutdown utility.
- [ ] Implement sleep utility.
- [ ] Implement system information utility.

### 088.3 Text and scripting utilities

- [ ] Implement file concatenation.
- [ ] Implement head and tail.
- [ ] Implement line and word counting.
- [ ] Implement text searching.
- [ ] Implement stream editing or a minimal equivalent.
- [ ] Implement sorting.
- [ ] Implement unique filtering.
- [ ] Implement cut and paste.
- [ ] Implement path basename and dirname.
- [ ] Implement expression evaluation.
- [ ] Implement true and false utilities.
- [ ] Implement echo and printf.
- [ ] Implement test expression utility.
- [ ] Implement xargs-like execution only with safe quoting semantics.
- [ ] Implement find utility.
- [ ] Implement a basic text editor.
- [ ] Document shell quoting and encoding rules.

## 089. PID 1, Init, and Service Manager

### 089.1 PID 1 responsibilities

- [ ] Become the first user-space process.
- [ ] Mount required pseudo filesystems.
- [ ] Mount persistent root if switching from initramfs.
- [ ] Perform root pivot or equivalent.
- [ ] Set hostname.
- [ ] Initialize system identity.
- [ ] Initialize logging.
- [ ] Initialize device manager.
- [ ] Load required firmware.
- [ ] Start storage services.
- [ ] Start entropy service if separate.
- [ ] Start time service.
- [ ] Start network services.
- [ ] Start authentication services.
- [ ] Start graphical services.
- [ ] Start PDC services in observer-only mode by default.
- [ ] Reap orphaned child processes.
- [ ] Handle service exit.
- [ ] Handle system shutdown request.
- [ ] Handle reboot request.
- [ ] Handle emergency mode.
- [ ] Handle single-user recovery mode.
- [ ] Remain functional when optional services fail.

### 089.2 Service definition format

- [ ] Define service name.
- [ ] Define executable.
- [ ] Define arguments.
- [ ] Define environment.
- [ ] Define working directory.
- [ ] Define user and group.
- [ ] Define capabilities.
- [ ] Define filesystem access.
- [ ] Define device access.
- [ ] Define network access.
- [ ] Define IPC endpoints.
- [ ] Define dependencies.
- [ ] Define ordering constraints.
- [ ] Define conditions.
- [ ] Define startup timeout.
- [ ] Define stop timeout.
- [ ] Define restart policy.
- [ ] Define restart backoff.
- [ ] Define health check.
- [ ] Define resource limits.
- [ ] Define CPU affinity.
- [ ] Define logging destination.
- [ ] Define secrets injection.
- [ ] Define update behavior.
- [ ] Define shutdown behavior.
- [ ] Version service definitions.
- [ ] Validate definitions before activation.

### 089.3 Dependency and transaction engine

- [ ] Build dependency graph.
- [ ] Detect cycles.
- [ ] Distinguish required and optional dependencies.
- [ ] Support parallel startup when ordering permits.
- [ ] Start dependency closure transactionally.
- [ ] Roll back partially started units when required.
- [ ] Stop reverse dependency closure safely.
- [ ] Handle dependency failure.
- [ ] Handle service activation by IPC, socket, path, timer, or device only if implemented.
- [ ] Prevent activation storms.
- [ ] Track service state transitions.
- [ ] Expose state and failure reason.
- [ ] Persist failure summaries across reboot.

### 089.4 Supervision

- [ ] Track main process.
- [ ] Track child processes.
- [ ] Track readiness notification.
- [ ] Track watchdog heartbeat.
- [ ] Track clean exit.
- [ ] Track crash exit.
- [ ] Track timeout.
- [ ] Track resource-limit termination.
- [ ] Capture stdout and stderr.
- [ ] Apply restart policy.
- [ ] Apply exponential backoff.
- [ ] Detect crash loops.
- [ ] Enter failed state after configured limit.
- [ ] Allow manual reset.
- [ ] Create per-service crash receipts.

## 090. Required System Processes and Daemons

### 090.1 Early and core system processes

- [ ] Implement `init` or equivalent PID 1.
- [ ] Implement service manager.
- [ ] Implement device manager.
- [ ] Implement hotplug event manager.
- [ ] Implement firmware loader service if not kernel-resident.
- [ ] Implement system logger.
- [ ] Implement kernel-log collector.
- [ ] Implement crash-dump collector.
- [ ] Implement hardware error collector.
- [ ] Implement entropy-seed persistence service.
- [ ] Implement clock and time synchronization service.
- [ ] Implement mount manager.
- [ ] Implement removable-media manager.
- [ ] Implement storage health monitor.
- [ ] Implement filesystem scrub scheduler if supported.
- [ ] Implement update agent.
- [ ] Implement package transaction service.
- [ ] Implement watchdog service.
- [ ] Implement power management service.
- [ ] Implement thermal policy service without overriding hardware safety.
- [ ] Implement session accounting service.
- [ ] Implement privilege-broker service.
- [ ] Implement secret-storage service.

### 090.2 Network processes

- [ ] Implement network manager.
- [ ] Implement DHCPv4 client.
- [ ] Implement DHCPv6 client if targeted.
- [ ] Implement IPv6 router-advertisement client if not in kernel.
- [ ] Implement DNS resolver or caching service.
- [ ] Implement Wi-Fi supplicant and authenticator client.
- [ ] Implement Bluetooth manager.
- [ ] Implement firewall rule manager.
- [ ] Implement time synchronization client.
- [ ] Implement certificate-store updater.
- [ ] Implement VPN manager if targeted.
- [ ] Implement captive-network assistant only with user consent.
- [ ] Implement network diagnostic service only if required.

### 090.3 User-session and desktop processes

- [ ] Implement login manager.
- [ ] Implement graphical display manager.
- [ ] Implement user session manager.
- [ ] Implement compositor or window server.
- [ ] Implement desktop shell.
- [ ] Implement notification daemon.
- [ ] Implement clipboard service.
- [ ] Implement settings service.
- [ ] Implement settings synchronization only with explicit opt-in.
- [ ] Implement audio server.
- [ ] Implement media-session policy service.
- [ ] Implement font service or cache builder.
- [ ] Implement accessibility bus or service.
- [ ] Implement input-method service.
- [ ] Implement screen-lock service.
- [ ] Implement power and idle agent.
- [ ] Implement file-indexing service only as optional and bounded.
- [ ] Implement thumbnail service in a sandbox.
- [ ] Implement desktop portal or permission broker.
- [ ] Implement crash-report user agent with opt-in upload.

### 090.4 PDC-specific processes

- [ ] Implement `pdc-observerd`.
- [ ] Implement `pdc-topologyd` if topology building is separate.
- [ ] Implement `pdc-modeld`.
- [ ] Implement `pdc-plannerd`.
- [ ] Implement `pdc-policyd`.
- [ ] Implement `pdc-actuatord`.
- [ ] Implement `pdc-watchdogd`.
- [ ] Implement `pdc-rollbackd`.
- [ ] Implement `pdc-receiptd`.
- [ ] Implement `pdc-verifierd` if continuous verification is required.
- [ ] Implement `pdc-claimd` for claim-boundary registry.
- [ ] Implement `pdc-benchmarkd` only under explicit user control.
- [ ] Implement PDC UI as an unprivileged client.
- [ ] Run observers with read-only rights.
- [ ] Run planner without actuator rights.
- [ ] Run actuator with narrowly scoped capabilities.
- [ ] Run watchdog independently from planner and actuator.
- [ ] Run rollback without dependence on the graphical session.

## 091. Device Manager and User-Space Hardware Policy

- [ ] Receive kernel device-add events.
- [ ] Receive kernel device-remove events.
- [ ] Receive driver-bind events.
- [ ] Receive firmware-request events.
- [ ] Populate device nodes.
- [ ] Set device ownership and permissions.
- [ ] Apply stable naming rules.
- [ ] Apply hardware quirks from signed database.
- [ ] Load user-space driver services if architecture supports them.
- [ ] Request module or driver load only through signed policy.
- [ ] Handle cold-plug enumeration at boot.
- [ ] Handle hot-plug during runtime.
- [ ] Serialize conflicting device policy actions.
- [ ] Expose detailed device state.
- [ ] Allow safe manual rebind.
- [ ] Allow safe device disable.
- [ ] Prevent unprivileged device impersonation.
- [ ] Log every privileged policy action.

## 092. Logging, Journaling, Audit, and Diagnostics

### 092.1 Structured logging

- [ ] Define log record schema.
- [ ] Include realtime timestamp.
- [ ] Include monotonic timestamp.
- [ ] Include boot identifier.
- [ ] Include machine identifier.
- [ ] Include process identifier.
- [ ] Include thread identifier.
- [ ] Include user identifier.
- [ ] Include service identifier.
- [ ] Include subsystem.
- [ ] Include severity.
- [ ] Include message identifier.
- [ ] Include structured fields.
- [ ] Include source build ID.
- [ ] Support binary-safe field encoding.
- [ ] Enforce record-size limits.
- [ ] Rate-limit noisy sources.
- [ ] Preserve dropped-message counters.
- [ ] Support volatile logs.
- [ ] Support persistent logs.
- [ ] Rotate logs.
- [ ] Enforce storage quotas.
- [ ] Redact secrets.
- [ ] Protect integrity of security logs.
- [ ] Export logs for recovery.

### 092.2 Security audit

- [ ] Audit authentication success and failure.
- [ ] Audit privilege changes.
- [ ] Audit capability grants.
- [ ] Audit package installation and removal.
- [ ] Audit update installation and rollback.
- [ ] Audit boot signature failures.
- [ ] Audit Secure Boot state changes.
- [ ] Audit firewall changes.
- [ ] Audit device authorization.
- [ ] Audit firmware loads.
- [ ] Audit PDC actuator actions.
- [ ] Audit PDC policy changes.
- [ ] Audit key management operations.
- [ ] Audit security-label changes.
- [ ] Audit denied access according to rate limits.
- [ ] Protect audit trail from unprivileged modification.
- [ ] Define audit retention.
- [ ] Define audit export.

### 092.3 Hardware and kernel diagnostics

- [ ] Expose CPU feature report.
- [ ] Expose CPU topology report.
- [ ] Expose memory map report.
- [ ] Expose page allocator state.
- [ ] Expose virtual memory map.
- [ ] Expose interrupt routing.
- [ ] Expose interrupt counts.
- [ ] Expose timer source and health.
- [ ] Expose scheduler queues and latency.
- [ ] Expose device tree.
- [ ] Expose PCI configuration summary.
- [ ] Expose USB topology.
- [ ] Expose ACPI table summary.
- [ ] Expose IOMMU domains and faults.
- [ ] Expose block queues and errors.
- [ ] Expose network statistics.
- [ ] Expose graphics and display state.
- [ ] Expose audio state.
- [ ] Expose thermal and power state.
- [ ] Expose active PDC policies.
- [ ] Restrict sensitive addresses and secrets.

## 093. Authentication, Login, and Session Management

### 093.1 Account database

- [ ] Define account record format.
- [ ] Define user identifier allocation.
- [ ] Define group record format.
- [ ] Define supplementary group membership.
- [ ] Define home directory.
- [ ] Define login shell.
- [ ] Define account lock state.
- [ ] Define password-change state.
- [ ] Define account expiration.
- [ ] Define service accounts.
- [ ] Define system accounts.
- [ ] Store account database with integrity protection.
- [ ] Lock database transactions.
- [ ] Provide account creation tool.
- [ ] Provide account deletion tool.
- [ ] Provide group management tool.
- [ ] Prevent identifier reuse hazards.

### 093.2 Password and credential handling

- [ ] Use a modern memory-hard password hashing algorithm.
- [ ] Generate unique salts.
- [ ] Store algorithm and parameters with hash.
- [ ] Set minimum work factors.
- [ ] Support parameter upgrades on successful login.
- [ ] Rate-limit failed authentication.
- [ ] Add delay without enabling trivial denial of service.
- [ ] Protect password input from terminal echo.
- [ ] Zero plaintext passwords after use.
- [ ] Prevent passwords from entering logs.
- [ ] Support recovery credentials.
- [ ] Support hardware-backed credentials later.
- [ ] Define multi-factor framework if targeted.
- [ ] Create modular authentication interface.
- [ ] Audit authentication events.

### 093.3 Login sessions

- [ ] Create text-console login.
- [ ] Create graphical login.
- [ ] Verify account and credentials.
- [ ] Apply account policy.
- [ ] Create user credentials.
- [ ] Create session process.
- [ ] Set environment.
- [ ] Set working directory.
- [ ] Mount user resources if required.
- [ ] Start per-user service manager.
- [ ] Track active sessions.
- [ ] Support session switching.
- [ ] Support session lock.
- [ ] Support logout.
- [ ] Terminate or preserve user services according to policy.
- [ ] Clean temporary session resources.
- [ ] Record session start and end.
- [ ] Prevent session fixation.

### 093.4 Privilege elevation

- [ ] Define privilege elevation policy.
- [ ] Authenticate requester when required.
- [ ] Authorize exact command or operation.
- [ ] Preserve only safe environment variables.
- [ ] Set audit identity distinct from effective identity.
- [ ] Use a narrow broker rather than broad permanent privilege.
- [ ] Apply timeout to cached authorization.
- [ ] Allow policy revocation.
- [ ] Log command, requester, target identity, and result.
- [ ] Prevent shell injection in broker protocol.
- [ ] Provide graphical and command-line authorization agents.

## 094. Shell, Terminal, PTY, and Job Control

### 094.1 Terminal subsystem

- [ ] Define terminal line discipline.
- [ ] Implement canonical input mode.
- [ ] Implement noncanonical input mode.
- [ ] Implement echo modes.
- [ ] Implement control-character handling.
- [ ] Implement input and output flags.
- [ ] Implement terminal window size.
- [ ] Implement foreground process group.
- [ ] Generate terminal signals.
- [ ] Implement hangup behavior.
- [ ] Implement pseudo-terminal master.
- [ ] Implement pseudo-terminal slave.
- [ ] Implement terminal multiplexing APIs.
- [ ] Support UTF-8 input and output.
- [ ] Prevent escape-sequence injection in privileged logs and prompts.

### 094.2 Shell

- [ ] Implement lexical analysis.
- [ ] Implement quoting.
- [ ] Implement escaping.
- [ ] Implement variable expansion.
- [ ] Implement command substitution only when designed safely.
- [ ] Implement wildcard expansion.
- [ ] Implement redirections.
- [ ] Implement pipelines.
- [ ] Implement background execution.
- [ ] Implement command sequencing.
- [ ] Implement conditional execution.
- [ ] Implement subshells if targeted.
- [ ] Implement shell variables.
- [ ] Implement exported environment.
- [ ] Implement built-ins.
- [ ] Implement exit status.
- [ ] Implement signal handling.
- [ ] Implement interactive history with privacy controls.
- [ ] Implement line editing.
- [ ] Implement completion only after basic parser stability.
- [ ] Document deviations from POSIX shell syntax.
- [ ] Fuzz shell parser.

### 094.3 Job control

- [ ] Create process groups for pipelines.
- [ ] Create sessions.
- [ ] Set foreground process group.
- [ ] Stop background jobs that read terminal according to policy.
- [ ] Handle interrupt character.
- [ ] Handle suspend character.
- [ ] Handle continued jobs.
- [ ] Track jobs.
- [ ] Implement foreground command.
- [ ] Implement background command.
- [ ] Implement jobs listing.
- [ ] Reap completed jobs.
- [ ] Handle shell exit with active jobs.

## 095. Package Format and Package Manager

### 095.1 Package format

- [ ] Assign package format version.
- [ ] Define package identity.
- [ ] Define architecture field.
- [ ] Define version format.
- [ ] Define release or revision field.
- [ ] Define dependencies.
- [ ] Define optional dependencies.
- [ ] Define conflicts.
- [ ] Define provides.
- [ ] Define replacements.
- [ ] Define file manifest.
- [ ] Define directory manifest.
- [ ] Define ownership and permissions.
- [ ] Define capabilities and security labels.
- [ ] Define configuration-file markers.
- [ ] Define service definitions.
- [ ] Define triggers or hooks under strict policy.
- [ ] Define licenses.
- [ ] Define source provenance.
- [ ] Define build provenance.
- [ ] Define SBOM attachment.
- [ ] Define content hashes.
- [ ] Define package signature.
- [ ] Define compression.
- [ ] Prevent path traversal and absolute-path escapes.
- [ ] Prevent special-file creation without authorization.
- [ ] Fuzz package parser.

### 095.2 Repository metadata

- [ ] Define repository identity.
- [ ] Define release channels.
- [ ] Define package index format.
- [ ] Define package metadata hashes.
- [ ] Define snapshot identifier.
- [ ] Define expiration or freshness policy.
- [ ] Sign repository metadata.
- [ ] Support key rotation.
- [ ] Support key revocation.
- [ ] Protect against freeze attacks.
- [ ] Protect against rollback attacks.
- [ ] Protect against mix-and-match metadata attacks.
- [ ] Mirror metadata safely.
- [ ] Support offline repository snapshots.
- [ ] Verify all content before installation.

### 095.3 Transaction engine

- [ ] Resolve dependencies deterministically.
- [ ] Explain dependency conflicts.
- [ ] Calculate installation plan.
- [ ] Display requested and transitive changes.
- [ ] Download to staging area.
- [ ] Verify hashes and signatures.
- [ ] Check disk space.
- [ ] Unpack without activating.
- [ ] Validate paths and metadata.
- [ ] Run package tests or preflight checks.
- [ ] Commit filesystem changes atomically where possible.
- [ ] Update package database atomically.
- [ ] Activate services only after commit.
- [ ] Roll back failed transaction.
- [ ] Preserve configuration files according to explicit rules.
- [ ] Handle interrupted transaction on reboot.
- [ ] Keep transaction journal.
- [ ] Support dry run.
- [ ] Support package verification.
- [ ] Support package repair.
- [ ] Support package removal.
- [ ] Support orphan cleanup.
- [ ] Support downgrade only under signed policy.

## 096. System Update Architecture

### 096.1 Atomic system images

- [ ] Choose A/B partitions, immutable snapshots, content-addressed trees, or equivalent atomic model.
- [ ] Separate system image from user data.
- [ ] Build update into inactive slot.
- [ ] Verify update manifest.
- [ ] Verify every artifact hash.
- [ ] Verify signatures.
- [ ] Verify minimum bootloader version.
- [ ] Verify minimum firmware version.
- [ ] Verify required disk space.
- [ ] Verify hardware compatibility.
- [ ] Run offline preflight checks.
- [ ] Write inactive slot completely.
- [ ] Flush storage.
- [ ] Mark slot pending.
- [ ] Set bounded boot-attempt count.
- [ ] Boot pending slot.
- [ ] Run post-boot health checks.
- [ ] Mark slot good only after checks pass.
- [ ] Roll back automatically after failed attempts.
- [ ] Retain previous known-good slot.
- [ ] Garbage-collect old images only after confirmation.

### 096.2 Update security

- [ ] Use offline root keys.
- [ ] Use delegated online metadata keys.
- [ ] Rotate keys.
- [ ] Revoke compromised keys.
- [ ] Pin repository identity.
- [ ] Use secure transport in addition to signatures.
- [ ] Prevent rollback below security floor.
- [ ] Prevent cross-edition image installation.
- [ ] Prevent cross-architecture image installation.
- [ ] Bind update to expected product and hardware class.
- [ ] Authenticate recovery updates.
- [ ] Log update provenance.
- [ ] Provide reproducible source references.
- [ ] Create emergency revocation channel.
- [ ] Test malicious metadata corpus.

### 096.3 Configuration and data migration

- [ ] Version every persistent configuration schema.
- [ ] Version every persistent database schema.
- [ ] Provide forward migrations.
- [ ] Provide rollback-compatible migrations or snapshot data before migration.
- [ ] Make migrations idempotent.
- [ ] Record migration completion.
- [ ] Handle partial migration.
- [ ] Validate data before and after migration.
- [ ] Preserve user changes.
- [ ] Separate generated and user-owned configuration.
- [ ] Test upgrade from every supported prior release.
- [ ] Test rollback after migration.

## 097. Installer

### 097.1 Installer environment

- [ ] Boot from signed live media.
- [ ] Run installer separately from target root.
- [ ] Provide serial and graphical modes.
- [ ] Inventory hardware.
- [ ] Verify minimum requirements.
- [ ] Verify target storage health.
- [ ] Detect existing operating systems.
- [ ] Detect encrypted volumes without destroying them.
- [ ] Back up partition table before changes.
- [ ] Provide explicit destructive-action warnings.
- [ ] Require exact disk selection.
- [ ] Display disk model, serial, and size.
- [ ] Support dry-run installation plan.
- [ ] Write complete installation log.
- [ ] Allow log export before reboot.

### 097.2 Partitioning and formatting

- [ ] Support using an entire spare disk first.
- [ ] Create GPT.
- [ ] Create EFI System Partition.
- [ ] Create active and inactive system slots if required.
- [ ] Create user-data partition.
- [ ] Create recovery partition.
- [ ] Create crash-dump area.
- [ ] Align partitions.
- [ ] Format filesystems.
- [ ] Initialize encryption.
- [ ] Generate recovery key.
- [ ] Verify formatted volumes.
- [ ] Write bootloader.
- [ ] Create UEFI boot entry.
- [ ] Install removable fallback boot path.
- [ ] Preserve existing ESP files when dual booting.
- [ ] Never overwrite unknown partitions without explicit consent.

### 097.3 System population

- [ ] Install base system image.
- [ ] Install kernel.
- [ ] Install initramfs.
- [ ] Install drivers.
- [ ] Install firmware.
- [ ] Install package database.
- [ ] Install recovery tools.
- [ ] Install root certificates.
- [ ] Install timezone and locale data.
- [ ] Create machine identity.
- [ ] Create first user.
- [ ] Set authentication credentials.
- [ ] Set hostname.
- [ ] Set locale.
- [ ] Set timezone.
- [ ] Configure keyboard.
- [ ] Configure network only with consent.
- [ ] Generate initial boot receipt.
- [ ] Verify installed-file hashes.
- [ ] Unmount cleanly.
- [ ] Set first-boot state.

### 097.4 Installation failure and recovery

- [ ] Handle power loss during partitioning.
- [ ] Handle power loss during formatting.
- [ ] Handle power loss during system copy.
- [ ] Handle full disk.
- [ ] Handle bad sectors.
- [ ] Handle signature failure.
- [ ] Handle incompatible firmware.
- [ ] Handle boot-entry creation failure.
- [ ] Restore partition table backup when safe.
- [ ] Leave target in an explicitly incomplete state.
- [ ] Never report success without boot verification.
- [ ] Offer repair or restart.
- [ ] Test installation in virtual and physical environments.

## 098. Recovery Environment

- [ ] Boot independently from the active system slot.
- [ ] Boot with all PDC actuation disabled.
- [ ] Boot with native GPU driver disabled.
- [ ] Use firmware framebuffer.
- [ ] Use simple USB input.
- [ ] Mount system volumes read-only by default.
- [ ] Unlock encrypted volumes with recovery key.
- [ ] Inspect boot status.
- [ ] Reset boot-attempt counters.
- [ ] Select previous known-good slot.
- [ ] Verify system image hashes.
- [ ] Repair bootloader files.
- [ ] Repair UEFI boot entries.
- [ ] Export logs.
- [ ] Export crash dumps.
- [ ] Export PDC receipts.
- [ ] Run filesystem check.
- [ ] Run filesystem repair only with explicit confirmation.
- [ ] Restore system image without deleting user data.
- [ ] Reset broken configuration.
- [ ] Disable a service.
- [ ] Disable a driver.
- [ ] Quarantine a package.
- [ ] Reset network configuration.
- [ ] Reset graphical configuration.
- [ ] Change or recover account credentials under secure physical-presence policy.
- [ ] Provide shell and scripted repair mode.
- [ ] Record every recovery action.
- [ ] Test recovery after each release.

## 099. Shutdown, Reboot, Suspend, and Hibernation

### 099.1 Orderly shutdown

- [ ] Broadcast shutdown request.
- [ ] Stop user sessions.
- [ ] Stop user services.
- [ ] Stop network services.
- [ ] Stop graphical services.
- [ ] Stop PDC actuator before storage teardown.
- [ ] Flush application data.
- [ ] Stop system services in dependency order.
- [ ] Unmount removable filesystems.
- [ ] Remount or unmount root safely.
- [ ] Flush filesystem metadata.
- [ ] Flush block devices.
- [ ] Issue NVMe shutdown notification.
- [ ] Stop DMA devices.
- [ ] Disable interrupts as appropriate.
- [ ] Record clean shutdown marker.
- [ ] Invoke ACPI S5.
- [ ] Fall back to reboot or halt if power-off fails.
- [ ] Watchdog shutdown timeout.

### 099.2 Reboot

- [ ] Attempt ACPI reset register.
- [ ] Attempt UEFI ResetSystem if runtime services are retained.
- [ ] Attempt keyboard-controller reset only as legacy fallback.
- [ ] Attempt triple fault only as last-resort fallback.
- [ ] Record reboot reason.
- [ ] Flush persistent state before reset.
- [ ] Test warm and cold reboot repeatedly.

### 099.3 Suspend to RAM

- [ ] Define supported sleep state.
- [ ] Quiesce user space.
- [ ] Freeze tasks.
- [ ] Stop PDC actuators.
- [ ] Sync filesystems.
- [ ] Suspend devices in dependency order.
- [ ] Save interrupt routing.
- [ ] Save timekeeping state.
- [ ] Save CPU state.
- [ ] Prepare ACPI sleep state.
- [ ] Enter S3 only on supported firmware.
- [ ] Resume bootstrap CPU.
- [ ] Restore memory mappings.
- [ ] Restore CPUs.
- [ ] Restore interrupt controllers.
- [ ] Restore timers.
- [ ] Resume devices in dependency order.
- [ ] Reinitialize devices that lose state.
- [ ] Adjust clocks for elapsed suspend time.
- [ ] Thaw tasks.
- [ ] Validate storage and network state.
- [ ] Fall back safely after resume failure.
- [ ] Test hundreds of cycles before support claim.

### 099.4 Hibernation

- [ ] Decide whether hibernation is in scope.
- [ ] Define image format.
- [ ] Define image authentication.
- [ ] Define image encryption.
- [ ] Define excluded pages.
- [ ] Freeze tasks.
- [ ] Quiesce devices.
- [ ] Write image transactionally.
- [ ] Flush image storage.
- [ ] Set resume marker.
- [ ] Power off.
- [ ] Verify hardware identity on resume.
- [ ] Verify kernel and image compatibility.
- [ ] Verify image integrity.
- [ ] Restore memory without overwriting resume code.
- [ ] Restore devices.
- [ ] Invalidate image after successful resume.
- [ ] Reject stale or tampered images.
- [ ] Test power failure during image creation.

## 100. Power, Frequency, Thermal, and Energy Management

- [ ] Define platform power-policy service.
- [ ] Expose CPU idle-state information.
- [ ] Expose CPU performance-state information.
- [ ] Use ACPI CPPC or documented mechanisms where applicable.
- [ ] Respect firmware and silicon safety limits.
- [ ] Read temperature sensors only through documented interfaces.
- [ ] Read critical trip points.
- [ ] Honor hardware thermal throttling.
- [ ] Honor emergency shutdown.
- [ ] Avoid undocumented voltage control.
- [ ] Avoid automatic overclocking.
- [ ] Avoid fan control unless hardware interface and failsafe are proven.
- [ ] Implement balanced policy.
- [ ] Implement performance policy.
- [ ] Implement power-saving policy.
- [ ] Implement user-selected policy.
- [ ] Account wakeups.
- [ ] Account residency in idle states.
- [ ] Account frequency residency.
- [ ] Account device power states.
- [ ] Measure energy only with calibrated sources.
- [ ] Handle power-source changes on future mobile targets.
- [ ] Test policy under sustained thermal load.
- [ ] Disable PDC actuation on thermal or power invariant breach.

## 101. Graphical Window System and Compositor

### 101.1 Display server protocol

- [ ] Define client connection transport.
- [ ] Define client authentication.
- [ ] Define protocol object IDs.
- [ ] Define request and event encoding.
- [ ] Define message length limits.
- [ ] Define version negotiation.
- [ ] Define global object discovery.
- [ ] Define surface object.
- [ ] Define buffer attachment.
- [ ] Define damage regions.
- [ ] Define frame callbacks.
- [ ] Define output objects.
- [ ] Define seat objects.
- [ ] Define keyboard objects.
- [ ] Define pointer objects.
- [ ] Define touch objects.
- [ ] Define clipboard objects.
- [ ] Define drag-and-drop objects.
- [ ] Define window role objects.
- [ ] Define popup behavior.
- [ ] Define protocol error handling.
- [ ] Disconnect malformed clients.
- [ ] Fuzz protocol decoder.

### 101.2 Compositor core

- [ ] Acquire display ownership.
- [ ] Enumerate outputs.
- [ ] Choose display modes.
- [ ] Create scanout buffers.
- [ ] Composite surfaces.
- [ ] Track damage.
- [ ] Clip drawing.
- [ ] Synchronize client buffers.
- [ ] Schedule frames to vblank.
- [ ] Handle missed deadlines.
- [ ] Handle page flips.
- [ ] Handle cursor plane.
- [ ] Handle output hotplug.
- [ ] Handle multi-monitor coordinates.
- [ ] Handle scaling.
- [ ] Handle rotation.
- [ ] Handle color spaces.
- [ ] Handle HDR only after complete pipeline support.
- [ ] Handle variable refresh only after correct presentation timing.
- [ ] Fall back to software composition.
- [ ] Recover from GPU reset.
- [ ] Protect secure surfaces from screenshots if policy supports it.

### 101.3 Window management

- [ ] Define top-level windows.
- [ ] Define transient windows.
- [ ] Define modal relationships.
- [ ] Define popups.
- [ ] Define focus policy.
- [ ] Define activation policy.
- [ ] Define stacking.
- [ ] Define workspaces.
- [ ] Define tiling or floating behavior.
- [ ] Define window decorations.
- [ ] Define resize constraints.
- [ ] Define fullscreen behavior.
- [ ] Define minimize and restore.
- [ ] Define attention requests.
- [ ] Prevent focus stealing.
- [ ] Constrain popups to visible outputs.
- [ ] Handle client hangs.
- [ ] Handle client disconnect.
- [ ] Provide accessibility metadata.

### 101.4 Input dispatch

- [ ] Map physical input devices to seats.
- [ ] Apply keymap.
- [ ] Track modifiers.
- [ ] Track key repeat.
- [ ] Dispatch keyboard focus.
- [ ] Dispatch pointer focus.
- [ ] Apply pointer acceleration.
- [ ] Constrain pointer.
- [ ] Support relative pointer for games if targeted.
- [ ] Support pointer capture with user-visible policy.
- [ ] Dispatch touch sequences.
- [ ] Handle gestures if implemented.
- [ ] Implement secure attention sequence outside normal clients.
- [ ] Prevent synthetic input from crossing permission boundaries.
- [ ] Handle device removal with state cleanup.

## 102. Fonts, Text Rendering, Localization, and Input Methods

### 102.1 Font stack

- [ ] Define font file formats accepted.
- [ ] Sandbox font parsing.
- [ ] Implement or port TrueType/OpenType parser.
- [ ] Implement glyph outline rasterization.
- [ ] Implement hinting policy.
- [ ] Implement antialiasing.
- [ ] Implement subpixel rendering only with output-aware policy.
- [ ] Implement font fallback.
- [ ] Implement font matching.
- [ ] Implement font cache.
- [ ] Invalidate cache on font updates.
- [ ] Parse variation fonts only if supported.
- [ ] Parse color fonts only if supported.
- [ ] Fuzz font parsers.

### 102.2 Unicode and shaping

- [ ] Use a pinned Unicode Character Database version.
- [ ] Implement UTF-8 decoding with strict validation.
- [ ] Implement grapheme cluster segmentation.
- [ ] Implement word segmentation.
- [ ] Implement line breaking.
- [ ] Implement bidirectional text.
- [ ] Implement normalization where needed.
- [ ] Implement script detection.
- [ ] Implement case mapping.
- [ ] Implement case folding.
- [ ] Implement collation if required.
- [ ] Implement shaping or port a reviewed shaping engine.
- [ ] Support combining marks.
- [ ] Support complex scripts only when shaping tests pass.
- [ ] Support emoji sequences only when font and segmentation support exist.
- [ ] Prevent Unicode spoofing in security-sensitive identifiers.
- [ ] Display escaped or normalized forms in security prompts.

### 102.3 Localization

- [ ] Define message catalog format.
- [ ] Define locale naming.
- [ ] Load locale data.
- [ ] Format numbers.
- [ ] Format currencies.
- [ ] Format dates and times.
- [ ] Format plural forms.
- [ ] Support right-to-left layout.
- [ ] Support localized keyboard layouts.
- [ ] Support translated installer and recovery text only with review.
- [ ] Provide English fallback for critical recovery errors.
- [ ] Version translations with source strings.

### 102.4 Input methods

- [ ] Define text-input protocol.
- [ ] Define composition events.
- [ ] Define preedit text.
- [ ] Define committed text.
- [ ] Define candidate list.
- [ ] Define surrounding-text access limits.
- [ ] Implement dead keys.
- [ ] Implement compose sequences.
- [ ] Support IME service isolation.
- [ ] Prevent untrusted applications from reading other applications' composition state.

## 103. Desktop Shell and User Experience

- [ ] Implement panel or status area.
- [ ] Implement application launcher.
- [ ] Implement task switching.
- [ ] Implement system tray or status-item protocol only with security policy.
- [ ] Implement notification center.
- [ ] Implement system settings.
- [ ] Implement display settings.
- [ ] Implement audio settings.
- [ ] Implement network settings.
- [ ] Implement Bluetooth settings.
- [ ] Implement power settings.
- [ ] Implement account settings.
- [ ] Implement package and update settings.
- [ ] Implement PDC control center.
- [ ] Implement file manager.
- [ ] Implement terminal emulator.
- [ ] Implement screenshot tool.
- [ ] Implement screen recording only with explicit user consent.
- [ ] Implement lock screen.
- [ ] Implement logout, reboot, and shutdown UI.
- [ ] Implement first-run setup.
- [ ] Implement recovery status UI.
- [ ] Implement accessibility settings.
- [ ] Provide keyboard-only navigation.
- [ ] Provide high-contrast mode.
- [ ] Provide scalable text and UI.
- [ ] Avoid exposing unverified performance claims as facts.

## 104. Audio Server and Media Policy

- [ ] Create user-space audio server.
- [ ] Discover kernel audio devices.
- [ ] Open playback and capture streams.
- [ ] Negotiate hardware formats.
- [ ] Mix multiple playback clients.
- [ ] Route capture clients.
- [ ] Resample when required.
- [ ] Convert sample formats.
- [ ] Apply per-stream volume.
- [ ] Apply per-device volume.
- [ ] Apply mute.
- [ ] Select default devices.
- [ ] Handle hotplug.
- [ ] Handle jack changes.
- [ ] Handle Bluetooth audio profiles if supported.
- [ ] Measure and compensate latency.
- [ ] Prevent one client from reading another client's audio.
- [ ] Require permission for microphone capture.
- [ ] Display active microphone indicator.
- [ ] Handle server restart without full system reboot.
- [ ] Implement media-session policy service.
- [ ] Test low-latency and power-saving modes.

## 105. Printing, Scanning, Camera, and Optional Peripheral Services

- [ ] Decide whether printing is in scope.
- [ ] Define print spool format.
- [ ] Sandbox document rendering.
- [ ] Discover printers.
- [ ] Implement USB or network print transport.
- [ ] Implement driver or printer-description model.
- [ ] Expose queue management.
- [ ] Restrict printer administration.
- [ ] Decide whether scanning is in scope.
- [ ] Sandbox image acquisition and decoding.
- [ ] Decide whether camera support is in scope.
- [ ] Require camera permission.
- [ ] Display active camera indicator.
- [ ] Isolate codec and media parsers.
- [ ] Mark all omitted peripheral classes explicitly unsupported.

## 106. Application Model, SDK, Sandboxing, and Porting

### 106.1 Native application ABI

- [ ] Publish system call ABI.
- [ ] Publish C ABI.
- [ ] Publish dynamic-linker ABI.
- [ ] Publish threading ABI.
- [ ] Publish graphics API.
- [ ] Publish audio API.
- [ ] Publish input API.
- [ ] Publish filesystem API.
- [ ] Publish networking API.
- [ ] Publish IPC API.
- [ ] Publish service discovery API.
- [ ] Publish permissions API.
- [ ] Publish package metadata format.
- [ ] Publish application manifest format.
- [ ] Version every public interface.
- [ ] Provide compatibility guarantees.
- [ ] Provide deprecation windows.

### 106.2 SDK

- [ ] Provide cross compiler.
- [ ] Provide sysroot.
- [ ] Provide headers.
- [ ] Provide libraries.
- [ ] Provide linker scripts and startup objects.
- [ ] Provide package builder.
- [ ] Provide debugger.
- [ ] Provide emulator launcher.
- [ ] Provide API documentation.
- [ ] Provide examples.
- [ ] Provide templates.
- [ ] Provide symbol server.
- [ ] Provide crash-symbolization tool.
- [ ] Provide application signing tool.
- [ ] Provide package signing tool.
- [ ] Provide conformance tests.
- [ ] Provide IDE integration where practical.

### 106.3 Application sandbox

- [ ] Define application identity.
- [ ] Define package signer identity.
- [ ] Define requested permissions.
- [ ] Define granted permissions.
- [ ] Define filesystem sandbox.
- [ ] Define device sandbox.
- [ ] Define network sandbox.
- [ ] Define IPC namespace.
- [ ] Define process visibility.
- [ ] Define clipboard permission.
- [ ] Define camera permission.
- [ ] Define microphone permission.
- [ ] Define screen-capture permission.
- [ ] Define location permission if location exists.
- [ ] Define notification permission.
- [ ] Define background execution permission.
- [ ] Define autostart permission.
- [ ] Define privileged portal services.
- [ ] Provide user-visible permission prompts.
- [ ] Prevent prompt spoofing.
- [ ] Allow permission revocation.
- [ ] Audit sensitive grants.

### 106.4 Third-party porting

- [ ] Create porting guide.
- [ ] Create build-system adapters.
- [ ] Create POSIX compatibility library where useful.
- [ ] Port a simple command-line program first.
- [ ] Port a text editor.
- [ ] Port compression libraries.
- [ ] Port image libraries in sandboxes.
- [ ] Port TLS library.
- [ ] Port language runtimes.
- [ ] Port a browser engine only after process sandboxing, graphics, fonts, networking, TLS, audio, and IPC are mature.
- [ ] Track every downstream patch.
- [ ] Upstream portability patches where possible.
- [ ] Run third-party test suites.
- [ ] Record unsupported behavior.

## 107. Security Architecture and Threat Model

### 107.1 Threat inventory

- [ ] Model malicious user applications.
- [ ] Model malicious websites.
- [ ] Model malicious network peers.
- [ ] Model malicious Wi-Fi access points.
- [ ] Model malicious Bluetooth peers.
- [ ] Model malicious USB devices.
- [ ] Model malicious PCIe devices.
- [ ] Model DMA attacks.
- [ ] Model compromised packages.
- [ ] Model compromised mirrors.
- [ ] Model compromised build systems.
- [ ] Model stolen signing keys.
- [ ] Model compromised firmware.
- [ ] Model malicious or buggy device firmware.
- [ ] Model physical disk theft.
- [ ] Model evil-maid boot modification.
- [ ] Model credential theft.
- [ ] Model privilege escalation.
- [ ] Model kernel memory corruption.
- [ ] Model filesystem corruption.
- [ ] Model update rollback.
- [ ] Model denial of service.
- [ ] Model side channels.
- [ ] Model data remanence.
- [ ] Model malicious PDC policies.
- [ ] Model faulty PDC planners.
- [ ] Model compromised PDC actuators.
- [ ] Model PooleGlyph parser and compiler exploits.
- [ ] Document trust boundaries.
- [ ] Document assets.
- [ ] Document attacker capabilities.
- [ ] Document accepted residual risks.

### 107.2 Kernel hardening

- [ ] Enforce W^X.
- [ ] Enable NX.
- [ ] Enable SMEP.
- [ ] Enable SMAP.
- [ ] Enable UMIP where compatible.
- [ ] Randomize kernel base.
- [ ] Randomize kernel stack locations where practical.
- [ ] Randomize heap allocations where practical.
- [ ] Use stack canaries.
- [ ] Use fortified memory and string operations.
- [ ] Use read-only-after-init sections.
- [ ] Make function-pointer tables read-only after setup.
- [ ] Protect kernel page tables.
- [ ] Hide kernel pointers from unprivileged users.
- [ ] Restrict physical memory access.
- [ ] Restrict port I/O.
- [ ] Restrict MSR access.
- [ ] Restrict PCI configuration writes.
- [ ] Restrict device memory mapping.
- [ ] Implement hardened user-copy bounds.
- [ ] Implement allocator red zones and quarantine in hardened builds.
- [ ] Implement control-flow integrity if toolchain and ABI permit.
- [ ] Implement return-address protection available on target architecture where feasible.
- [ ] Implement speculation mitigations appropriate to target CPU and threat model.
- [ ] Separate user and kernel page tables if required by vulnerabilities and performance tradeoffs.
- [ ] Audit every kernel attack surface.
- [ ] Fuzz every untrusted parser.

### 107.3 Service hardening

- [ ] Run each service under a dedicated identity.
- [ ] Drop privileges after initialization.
- [ ] Grant only required capabilities.
- [ ] Restrict filesystem paths.
- [ ] Restrict devices.
- [ ] Restrict network access.
- [ ] Restrict IPC peers.
- [ ] Set memory and process limits.
- [ ] Disable core dumps for secret-bearing services unless encrypted secure dumps exist.
- [ ] Use read-only system image.
- [ ] Use private temporary directories.
- [ ] Use no-new-privileges policy.
- [ ] Use seccomp-like syscall filtering if implemented.
- [ ] Use address-space randomization.
- [ ] Use stack protection.
- [ ] Use sandboxed helper processes for complex parsers.
- [ ] Define restart and crash-loop policy.

## 108. Cryptography and Randomness

### 108.1 Entropy collection

- [ ] Define entropy-source registry.
- [ ] Collect bootloader-provided UEFI RNG output when available.
- [ ] Collect RDSEED output as one source when supported.
- [ ] Collect RDRAND output only as supplemental input.
- [ ] Collect interrupt timing only with conservative entropy estimates.
- [ ] Collect device timing only with conservative entropy estimates.
- [ ] Collect TPM random output if available.
- [ ] Collect user input timing only as supplemental input.
- [ ] Track source health.
- [ ] Run repetition and adaptive proportion health tests where appropriate.
- [ ] Do not credit deterministic or attacker-controlled data as entropy.
- [ ] Mix all sources with a cryptographic construction.
- [ ] Persist a seed across clean shutdown.
- [ ] Protect the persistent seed.
- [ ] Rotate seed after use.
- [ ] Refuse cryptographic key generation before sufficient initialization.
- [ ] Expose readiness state.

### 108.2 Kernel CSPRNG

- [ ] Choose a reviewed DRBG or stream-cipher construction.
- [ ] Define initialization requirements.
- [ ] Define reseed requirements.
- [ ] Define per-CPU generation state if used.
- [ ] Define fork or clone safety.
- [ ] Define backtracking resistance.
- [ ] Define prediction resistance policy.
- [ ] Mix new entropy safely.
- [ ] Prevent state rollback across snapshots where relevant.
- [ ] Provide blocking secure random API.
- [ ] Provide nonblocking status API.
- [ ] Provide fast noncryptographic random API separately.
- [ ] Zero replaced state.
- [ ] Test known vectors.
- [ ] Test failure behavior.
- [ ] Obtain independent review.

### 108.3 Cryptographic provider

- [ ] Define algorithm provider API.
- [ ] Define hash API.
- [ ] Define MAC API.
- [ ] Define symmetric cipher API.
- [ ] Define AEAD API.
- [ ] Define key-derivation API.
- [ ] Define public-key signature API.
- [ ] Define key-agreement API.
- [ ] Define post-quantum algorithm boundary only when standards and interoperability require it.
- [ ] Use constant-time implementations for secret-dependent operations.
- [ ] Detect CPU acceleration safely.
- [ ] Keep scalar reference implementations for verification.
- [ ] Run published test vectors.
- [ ] Run differential tests against independent implementations.
- [ ] Implement key object with usage restrictions.
- [ ] Implement secure key deletion.
- [ ] Version algorithm identifiers.
- [ ] Disable deprecated algorithms by policy.
- [ ] Do not create proprietary cryptographic primitives for security use without extensive independent cryptanalysis.

## 109. TPM 2.0 and Hardware-Backed Security

- [ ] Discover TPM through ACPI TPM2 table.
- [ ] Identify TPM interface type.
- [ ] Map command and response buffers.
- [ ] Implement locality handling.
- [ ] Implement command framing.
- [ ] Implement response parsing.
- [ ] Validate response sizes and codes.
- [ ] Implement startup command.
- [ ] Read capabilities.
- [ ] Read PCR values.
- [ ] Extend PCR values.
- [ ] Read random bytes.
- [ ] Create primary keys.
- [ ] Create sealed objects.
- [ ] Unseal with policy.
- [ ] Support NV indices only if required.
- [ ] Preserve and parse event log.
- [ ] Bind disk-unlock policy to measured boot only with recovery path.
- [ ] Bind device identity only with privacy consideration.
- [ ] Handle TPM clear and ownership changes.
- [ ] Handle missing or disabled TPM.
- [ ] Fuzz response parser.
- [ ] Never make TPM the only recovery path.

## 110. Secrets, Certificates, and Key Storage

- [ ] Create kernel key object or user-space secret service.
- [ ] Separate machine secrets from user secrets.
- [ ] Encrypt secrets at rest.
- [ ] Tie user secrets to user authentication.
- [ ] Tie machine secrets to TPM policy optionally.
- [ ] Define unlock and lock lifecycle.
- [ ] Zero secrets on session end.
- [ ] Prevent secrets from logs.
- [ ] Prevent secrets from swap unless encrypted.
- [ ] Prevent secrets from crash dumps.
- [ ] Limit secret access by application identity.
- [ ] Prompt users through trusted UI.
- [ ] Prevent clipboard leakage by default for protected secrets.
- [ ] Implement root certificate store.
- [ ] Implement certificate distrust list.
- [ ] Implement certificate update process.
- [ ] Implement application signing trust store.
- [ ] Implement package signing trust store.
- [ ] Implement boot signing trust store.
- [ ] Separate trust domains and keys.
- [ ] Provide key backup and recovery procedures.
- [ ] Audit key use.

## 111. Mandatory Access Control, Policy, and Security Labels

- [ ] Decide whether mandatory access control is required for initial release.
- [ ] Define subject labels.
- [ ] Define object labels.
- [ ] Define domains and types.
- [ ] Define transition rules.
- [ ] Define default-deny policy.
- [ ] Define policy language.
- [ ] Define policy compiler.
- [ ] Define kernel policy representation.
- [ ] Define policy versioning.
- [ ] Define policy signature.
- [ ] Define policy load timing.
- [ ] Prevent policy downgrade.
- [ ] Define permissive diagnostic mode with unmistakable warning.
- [ ] Log denials with rate limits.
- [ ] Provide policy query tools.
- [ ] Provide policy test simulator.
- [ ] Fuzz policy parser and compiler.
- [ ] Prove recovery remains possible under broken policy.
- [ ] Integrate PooleGlyph only after equivalent safety checks exist.

## 112. Privacy and Telemetry

- [ ] Define telemetry as disabled by default unless explicitly chosen otherwise.
- [ ] Inventory every data field that could leave the machine.
- [ ] Classify identifiers as direct, indirect, sensitive, or anonymous.
- [ ] Avoid stable device identifiers in public reports unless required.
- [ ] Obtain explicit consent before upload.
- [ ] Allow per-category consent.
- [ ] Allow local-only diagnostics.
- [ ] Allow review of exact payload before upload.
- [ ] Allow deletion of queued telemetry.
- [ ] Use encrypted transport.
- [ ] Authenticate telemetry endpoint.
- [ ] Rate-limit uploads.
- [ ] Minimize retention.
- [ ] Publish retention policy.
- [ ] Separate crash reports from usage analytics.
- [ ] Redact paths, usernames, secrets, and document content.
- [ ] Do not upload raw memory dumps automatically.
- [ ] Make PDC benchmark receipts local by default.
- [ ] Provide an offline export bundle.
- [ ] Document all network connections initiated by the OS.

## 113. Kernel and User-Space Debugging

### 113.1 Symbol and debug information

- [ ] Generate DWARF debug information.
- [ ] Generate build IDs.
- [ ] Generate separate debug symbol files.
- [ ] Store symbols by build ID.
- [ ] Preserve exact compiler and linker versions.
- [ ] Preserve source commit references.
- [ ] Preserve load addresses and relocation slides.
- [ ] Generate function and line tables.
- [ ] Generate frame-unwind information or frame pointers.
- [ ] Verify debug information against stripped binaries.
- [ ] Create symbol server or local symbol store.
- [ ] Restrict release access to proprietary or sensitive symbols if applicable.

### 113.2 Kernel debugger

- [ ] Implement debugger entry by breakpoint.
- [ ] Implement debugger entry by serial command.
- [ ] Implement debugger entry on panic.
- [ ] Stop other CPUs safely.
- [ ] Display registers.
- [ ] Display stack trace.
- [ ] Read memory.
- [ ] Write memory only in explicit unsafe mode.
- [ ] Inspect page tables.
- [ ] Inspect tasks.
- [ ] Inspect scheduler queues.
- [ ] Inspect locks.
- [ ] Inspect devices.
- [ ] Inspect interrupts.
- [ ] Inspect timers.
- [ ] Set software breakpoints.
- [ ] Set hardware breakpoints if supported.
- [ ] Single-step.
- [ ] Resume execution only when state is recoverable.
- [ ] Integrate GDB remote protocol if selected.
- [ ] Authenticate remote debugging on real systems.
- [ ] Disable remote debugging in production by default.

### 113.3 User-space debugger

- [ ] Implement process attach.
- [ ] Implement process launch under debugger.
- [ ] Implement memory read and write.
- [ ] Implement register read and write.
- [ ] Implement breakpoint insertion.
- [ ] Implement single-step.
- [ ] Implement thread enumeration.
- [ ] Implement signal or exception interception.
- [ ] Implement shared-library notifications.
- [ ] Implement core-dump loading.
- [ ] Implement DWARF symbol resolution.
- [ ] Implement source-level stack traces.
- [ ] Enforce debugger permissions.
- [ ] Prevent attaching to more privileged processes without authorization.

## 114. Crash Dumps and Postmortem Analysis

### 114.1 Kernel crash dump

- [ ] Reserve crash-dump storage.
- [ ] Define dump format.
- [ ] Version dump format.
- [ ] Include kernel build ID.
- [ ] Include panic code.
- [ ] Include registers for all CPUs.
- [ ] Include current tasks.
- [ ] Include selected memory ranges.
- [ ] Include kernel logs.
- [ ] Include module list.
- [ ] Include device state summaries.
- [ ] Include page-table roots.
- [ ] Include scheduler state.
- [ ] Include PDC active-policy state.
- [ ] Exclude encryption keys and secrets.
- [ ] Compress only with panic-safe code.
- [ ] Write through a minimal trusted storage path.
- [ ] Fall back to serial or network dump only under explicit configuration.
- [ ] Mark dump complete atomically.
- [ ] Detect and preserve dump on next boot.
- [ ] Provide dump extraction tool.
- [ ] Provide symbolization tool.
- [ ] Test dump generation under allocator, filesystem, and interrupt failures.

### 114.2 User-space core dumps

- [ ] Define core format.
- [ ] Include executable build ID.
- [ ] Include memory mappings.
- [ ] Include thread registers.
- [ ] Include signal or exception reason.
- [ ] Include selected memory segments.
- [ ] Exclude secret mappings by annotation.
- [ ] Apply size limits.
- [ ] Apply ownership and permissions.
- [ ] Store in per-user protected location.
- [ ] Allow opt-out.
- [ ] Create core inspection tool.

## 115. Performance Counters, Tracing, and Observability

### 115.1 Kernel trace framework

- [ ] Define trace event schema.
- [ ] Define event identifier.
- [ ] Define timestamp source.
- [ ] Define CPU identifier.
- [ ] Define thread identifier.
- [ ] Define event payload size limits.
- [ ] Implement per-CPU trace buffers.
- [ ] Implement lockless write path where safe.
- [ ] Implement overwrite and stop-on-full modes.
- [ ] Implement event filtering.
- [ ] Implement event sampling.
- [ ] Implement trace enable and disable.
- [ ] Implement user-space reader.
- [ ] Implement snapshot.
- [ ] Implement trace markers.
- [ ] Implement lost-event counters.
- [ ] Restrict sensitive events.
- [ ] Define stable and experimental tracepoints.

### 115.2 Required tracepoints

- [ ] Trace boot stages.
- [ ] Trace interrupt entry and exit.
- [ ] Trace timer expiry.
- [ ] Trace scheduler enqueue and dequeue.
- [ ] Trace context switches.
- [ ] Trace wakeups.
- [ ] Trace migrations.
- [ ] Trace page faults.
- [ ] Trace allocation and free in diagnostic modes.
- [ ] Trace block request issue and completion.
- [ ] Trace filesystem operations.
- [ ] Trace network transmit and receive.
- [ ] Trace driver resets.
- [ ] Trace GPU submission and completion when available.
- [ ] Trace frame composition and presentation.
- [ ] Trace audio buffer periods and xruns.
- [ ] Trace service start and stop.
- [ ] Trace update and rollback.
- [ ] Trace PDC observation, proposal, authorization, actuation, verification, and rollback.

### 115.3 CPU performance monitoring

- [ ] Discover performance-monitoring version and counter count.
- [ ] Define event-selection API.
- [ ] Define per-thread counters.
- [ ] Define per-CPU counters.
- [ ] Define sampling interrupts.
- [ ] Handle counter overflow.
- [ ] Virtualize counters across tasks.
- [ ] Restrict privileged events.
- [ ] Avoid exposing kernel addresses in samples.
- [ ] Support cycles.
- [ ] Support instructions.
- [ ] Support cache events only when accurately defined for target CPU.
- [ ] Support branch events only when accurately defined.
- [ ] Record multiplexing and scaling.
- [ ] Detect counter conflicts.
- [ ] Validate measurements against known workloads.
- [ ] Treat model-specific event semantics as hardware-versioned.

### 115.4 System metrics

- [ ] Expose CPU utilization.
- [ ] Expose run-queue depth.
- [ ] Expose scheduling latency.
- [ ] Expose context-switch rate.
- [ ] Expose interrupt rate.
- [ ] Expose memory usage.
- [ ] Expose memory pressure.
- [ ] Expose allocation failures.
- [ ] Expose page-fault rate.
- [ ] Expose block latency and throughput.
- [ ] Expose filesystem cache statistics.
- [ ] Expose network throughput, drops, retransmissions, and latency indicators.
- [ ] Expose GPU utilization and memory only when trustworthy.
- [ ] Expose display frame time and missed frames.
- [ ] Expose audio latency and xruns.
- [ ] Expose power and thermal telemetry only when trustworthy.
- [ ] Expose service health.
- [ ] Expose PDC overhead and benefit measurements separately.
- [ ] Version every metric definition.

## 116. Performance Methodology and Benchmark Integrity

- [ ] Define workload identity by source and hash.
- [ ] Define input identity by hash.
- [ ] Define output equivalence criteria.
- [ ] Define correctness oracle.
- [ ] Define baseline route.
- [ ] Define neutral control route.
- [ ] Define PDC route.
- [ ] Define warmup policy.
- [ ] Define cache state.
- [ ] Define process placement.
- [ ] Define CPU frequency policy.
- [ ] Define thermal stabilization.
- [ ] Define background-service state.
- [ ] Define network conditions.
- [ ] Define storage durability boundary.
- [ ] Define setup-cost boundary.
- [ ] Define teardown-cost boundary.
- [ ] Define sample count before running.
- [ ] Define outlier policy before running.
- [ ] Randomize route order.
- [ ] Record every failed run.
- [ ] Report median.
- [ ] Report mean.
- [ ] Report standard deviation or robust spread.
- [ ] Report p95 and p99 where relevant.
- [ ] Report confidence intervals where applicable.
- [ ] Report absolute time.
- [ ] Report time reduction percentage.
- [ ] Report speedup ratio.
- [ ] Report resource usage.
- [ ] Report setup overhead.
- [ ] Report rollback overhead.
- [ ] Report correctness failures.
- [ ] Report thermal and power state.
- [ ] Preserve raw measurements.
- [ ] Sign closeout receipts.
- [ ] Require independent reproduction before broad claims.

## 117. Poole Defect Calculus Control Plane

### 117.1 System boundaries

- [ ] Define PDC as an optional policy layer rather than an implicit kernel invariant.
- [ ] Define every observable input.
- [ ] Define every controllable output.
- [ ] Define every protected resource.
- [ ] Define every lane.
- [ ] Define every valid operating region.
- [ ] Define every forbidden operating region.
- [ ] Define every correctness invariant.
- [ ] Define every latency budget.
- [ ] Define every resource budget.
- [ ] Define every thermal budget.
- [ ] Define every setup-cost budget.
- [ ] Define every decision expiration.
- [ ] Define every rollback trigger.
- [ ] Define every fallback state.
- [ ] Define every claim boundary.
- [ ] Define every evidence class.
- [ ] Version all definitions.

### 117.2 PDC observer

- [ ] Run observer without actuator privileges.
- [ ] Use read-only kernel interfaces.
- [ ] Timestamp every observation.
- [ ] Record clock domain.
- [ ] Record sampling interval.
- [ ] Record missed samples.
- [ ] Record data freshness.
- [ ] Record sensor trust level.
- [ ] Record calibration state.
- [ ] Detect unavailable sensors.
- [ ] Detect stale sensors.
- [ ] Detect inconsistent sensors.
- [ ] Normalize units.
- [ ] Normalize topology identifiers.
- [ ] Avoid observer-induced load that dominates the workload.
- [ ] Measure observer overhead.
- [ ] Support deterministic trace replay.
- [ ] Sign or hash observation streams used for receipts.

### 117.3 PDC topology and model

- [ ] Define node types.
- [ ] Define edge types.
- [ ] Define resource identities.
- [ ] Define workload identities.
- [ ] Define queue identities.
- [ ] Define ownership relationships.
- [ ] Define locality relationships.
- [ ] Define dependency relationships.
- [ ] Define contention relationships.
- [ ] Define defect values.
- [ ] Define defect confidence.
- [ ] Define temporal decay.
- [ ] Define missing-data representation.
- [ ] Define model update rules.
- [ ] Validate model dimensions.
- [ ] Validate finite numeric values.
- [ ] Detect model divergence.
- [ ] Bound model memory.
- [ ] Version model schema.
- [ ] Serialize model snapshots for replay.

### 117.4 PDC planner

- [ ] Run planner without direct hardware access.
- [ ] Consume versioned observation and model inputs.
- [ ] Produce immutable action proposals.
- [ ] Include proposal identifier.
- [ ] Include target resource.
- [ ] Include requested action.
- [ ] Include preconditions.
- [ ] Include expected benefit.
- [ ] Include estimated setup cost.
- [ ] Include estimated duration.
- [ ] Include maximum duration.
- [ ] Include correctness invariant.
- [ ] Include rollback plan.
- [ ] Include confidence.
- [ ] Include evidence basis.
- [ ] Include expiration time.
- [ ] Include conflicting-resource set.
- [ ] Reject NaN, infinity, overflow, and invalid units.
- [ ] Limit planning CPU and memory usage.
- [ ] Handle planner timeout.
- [ ] Support deterministic planner replay.

### 117.5 PDC policy gate

- [ ] Authenticate planner identity.
- [ ] Validate proposal signature or channel authenticity.
- [ ] Validate schema version.
- [ ] Validate target existence.
- [ ] Validate target ownership.
- [ ] Validate action allowlist.
- [ ] Validate lane enabled state.
- [ ] Validate hardware support tier.
- [ ] Validate firmware version.
- [ ] Validate kernel and driver version.
- [ ] Validate current system state.
- [ ] Validate preconditions.
- [ ] Validate decision freshness.
- [ ] Validate resource budgets.
- [ ] Validate setup-cost threshold.
- [ ] Validate fairness constraints.
- [ ] Validate thermal constraints.
- [ ] Validate security constraints.
- [ ] Validate user consent.
- [ ] Validate conflict locks.
- [ ] Validate rollback availability.
- [ ] Validate watchdog availability.
- [ ] Reject on any uncertainty according to fail-closed policy.
- [ ] Record authorization or rejection reason.

### 117.6 PDC actuator

- [ ] Run with lane-specific capabilities only.
- [ ] Accept only authorized proposals.
- [ ] Revalidate proposal freshness.
- [ ] Acquire exclusive resource lease.
- [ ] Capture pre-action state.
- [ ] Create rollback checkpoint.
- [ ] Apply smallest possible action.
- [ ] Verify action took effect.
- [ ] Start action expiration timer.
- [ ] Expose health heartbeat.
- [ ] Stop action on cancellation.
- [ ] Stop action on watchdog request.
- [ ] Restore state on failure.
- [ ] Release resource lease.
- [ ] Record exact kernel calls and hardware operations.
- [ ] Never accept free-form register writes from policy input.
- [ ] Never accept arbitrary file paths or commands from policy input.
- [ ] Never control voltage or safety-critical limits without separately proven subsystem.

### 117.7 PDC watchdog

- [ ] Run independently from planner and actuator.
- [ ] Observe actuator heartbeat.
- [ ] Observe system scheduling progress.
- [ ] Observe input responsiveness.
- [ ] Observe storage completion.
- [ ] Observe network liveness where relevant.
- [ ] Observe display progress where relevant.
- [ ] Observe audio progress where relevant.
- [ ] Observe thermal limits.
- [ ] Observe memory pressure.
- [ ] Observe kernel error counters.
- [ ] Detect deadlock.
- [ ] Detect livelock.
- [ ] Detect starvation.
- [ ] Detect performance collapse.
- [ ] Detect correctness failure.
- [ ] Detect expired action.
- [ ] Request immediate rollback.
- [ ] Escalate to lane disable.
- [ ] Escalate to all-PDC disable.
- [ ] Escalate to safe-mode reboot only under explicit policy.
- [ ] Persist watchdog reason.
- [ ] Test watchdog under planner and actuator crashes.

### 117.8 PDC rollback

- [ ] Maintain canonical default state.
- [ ] Maintain pre-action state.
- [ ] Validate rollback target.
- [ ] Allow rollback without planner.
- [ ] Allow rollback without GUI.
- [ ] Allow rollback during partial service failure.
- [ ] Make rollback idempotent.
- [ ] Use bounded timeouts.
- [ ] Verify restored state.
- [ ] Escalate when restoration fails.
- [ ] Disable affected lane after failed rollback.
- [ ] Persist lane quarantine.
- [ ] Clear quarantine only through explicit reviewed action.
- [ ] Create rollback receipt.
- [ ] Test rollback at every intermediate actuator step.

### 117.9 PDC receipts and verifier

- [ ] Assign receipt identifier.
- [ ] Assign run identifier.
- [ ] Record UTC timestamp.
- [ ] Record monotonic time range.
- [ ] Record hardware manifest hash.
- [ ] Record firmware manifest.
- [ ] Record bootloader hash.
- [ ] Record kernel hash.
- [ ] Record driver hashes.
- [ ] Record PDC component hashes.
- [ ] Record PooleGlyph policy hash.
- [ ] Record workload hash.
- [ ] Record input hash.
- [ ] Record output hash or semantic verification result.
- [ ] Record baseline configuration.
- [ ] Record control configuration.
- [ ] Record PDC configuration.
- [ ] Record sample count.
- [ ] Record raw timing data reference.
- [ ] Record setup time.
- [ ] Record measured time.
- [ ] Record teardown time.
- [ ] Record resource usage.
- [ ] Record thermal state.
- [ ] Record observer overhead.
- [ ] Record planner overhead.
- [ ] Record actuator overhead.
- [ ] Record watchdog events.
- [ ] Record rollback events.
- [ ] Record invalid runs.
- [ ] Record claim boundary.
- [ ] Record promotion status.
- [ ] Sign receipt.
- [ ] Provide offline verifier.
- [ ] Reject altered or incomplete receipts.

## 118. PDC CPU and Scheduler Lane

- [ ] Define CPU lane inputs.
- [ ] Define runnable-work topology.
- [ ] Define cache-sharing topology.
- [ ] Define SMT topology.
- [ ] Define CCD and NUMA topology.
- [ ] Define task latency classes.
- [ ] Define task throughput classes.
- [ ] Define task affinity constraints.
- [ ] Define real-time exclusions.
- [ ] Define starvation limit.
- [ ] Define migration limit.
- [ ] Define wakeup delay limit.
- [ ] Define scheduler decision overhead limit.
- [ ] Implement observation-only mode.
- [ ] Implement proposal-only mode.
- [ ] Implement one bounded actuation primitive at a time.
- [ ] Implement CPU affinity change.
- [ ] Implement priority change only under policy.
- [ ] Implement queue placement only through scheduler API.
- [ ] Implement rollback to neutral scheduler.
- [ ] Verify no task loss.
- [ ] Verify no duplicate runnable task.
- [ ] Verify bounded scheduling latency.
- [ ] Verify fairness.
- [ ] Verify real-time isolation.
- [ ] Verify interactive responsiveness.
- [ ] Stress with CPU-bound, I/O-bound, wake-heavy, and mixed workloads.
- [ ] Count total wall time including policy overhead.

## 119. PDC Memory Lane

- [ ] Define memory lane inputs.
- [ ] Observe allocation rate.
- [ ] Observe page-fault rate.
- [ ] Observe reclaim rate.
- [ ] Observe working-set size.
- [ ] Observe NUMA locality.
- [ ] Observe cache pressure only with trustworthy counters.
- [ ] Define correctness as byte-for-byte or semantic output equivalence.
- [ ] Define maximum added memory.
- [ ] Define maximum reclaim latency.
- [ ] Define OOM safety policy.
- [ ] Implement read-ahead or placement proposal before allocator mutation.
- [ ] Implement page migration only with rollback and pin checks.
- [ ] Implement huge-page promotion only with fragmentation and latency controls.
- [ ] Implement cache retention policy only within pressure limits.
- [ ] Never skip required initialization, validation, copy, or synchronization.
- [ ] Verify no data leakage.
- [ ] Verify no use-after-free increase.
- [ ] Verify no swap thrash.
- [ ] Verify latency tails.
- [ ] Run memory-corruption sanitizers and stress tests.

## 120. PDC Storage and Filesystem Lane

- [ ] Define storage lane inputs.
- [ ] Observe request size.
- [ ] Observe queue depth.
- [ ] Observe latency distribution.
- [ ] Observe read/write ratio.
- [ ] Observe sequentiality.
- [ ] Observe flush and FUA boundaries.
- [ ] Observe application state.
- [ ] Define durability equivalence.
- [ ] Define ordering equivalence.
- [ ] Define crash-consistency equivalence.
- [ ] Define maximum buffering delay.
- [ ] Define maximum memory buffer.
- [ ] Implement batching only when durability semantics remain equal.
- [ ] Implement request reordering only across independent operations.
- [ ] Implement read-ahead only with bounded pollution.
- [ ] Implement write coalescing only before the same required persistence boundary.
- [ ] Implement application runtime path separately from raw block path.
- [ ] Never acknowledge persistence before the required device boundary.
- [ ] Power-cut test every claimed optimization.
- [ ] Hash outputs.
- [ ] Verify filesystem after adversarial interruption.
- [ ] Include setup and cache-warming cost.

## 121. PDC Network Lane

- [ ] Define network lane inputs.
- [ ] Observe application message boundaries.
- [ ] Observe MTU.
- [ ] Observe congestion window only through supported stack state.
- [ ] Observe loss.
- [ ] Observe retransmission.
- [ ] Observe RTT.
- [ ] Observe queueing delay.
- [ ] Observe radio and link state.
- [ ] Define protocol correctness.
- [ ] Define fairness to competing flows.
- [ ] Define congestion-control compliance.
- [ ] Define maximum intentional delay.
- [ ] Implement application batching only with latency limit.
- [ ] Implement segmentation scheduling without violating MTU or congestion control.
- [ ] Implement BLE transfer scheduling only in a separately validated profile.
- [ ] Never falsify acknowledgements.
- [ ] Never bypass encryption or integrity checks.
- [ ] Test loss, reordering, duplication, bandwidth changes, and disconnects.
- [ ] Measure goodput and tail latency.
- [ ] Include CPU and energy overhead.

## 122. PDC GPU and Display Lanes

### 122.1 GPU lane

- [ ] Define GPU lane inputs only from trustworthy driver telemetry.
- [ ] Observe queue occupancy.
- [ ] Observe submission latency.
- [ ] Observe completion latency.
- [ ] Observe memory pressure.
- [ ] Observe engine utilization.
- [ ] Observe thermal and power state.
- [ ] Define command-ordering invariants.
- [ ] Define memory-coherency invariants.
- [ ] Define synchronization invariants.
- [ ] Define maximum queue delay.
- [ ] Implement workload routing only through stable driver interfaces.
- [ ] Implement batching only when synchronization semantics are preserved.
- [ ] Never emit undocumented GPU commands from high-level policy input.
- [ ] Detect GPU hangs.
- [ ] Reset and fall back safely.
- [ ] Compare output hashes, image metrics, or exact compute results as appropriate.

### 122.2 Display composition lane

- [ ] Observe surface damage.
- [ ] Observe occlusion.
- [ ] Observe transforms.
- [ ] Observe opacity.
- [ ] Observe presentation deadlines.
- [ ] Observe scanout eligibility.
- [ ] Define exact visual-equivalence criteria.
- [ ] Define maximum stale-pixel tolerance as zero unless explicitly testing approximation.
- [ ] Track dirty tiles.
- [ ] Coalesce damage conservatively.
- [ ] Skip fully occluded surfaces only with correct region math.
- [ ] Promote direct scanout only when format, scaling, color, and security constraints match.
- [ ] Fall back on any uncertainty.
- [ ] Capture frame hashes in deterministic tests.
- [ ] Capture screenshots for visual diff.
- [ ] Measure CPU time, GPU time, memory bandwidth, and frame latency.
- [ ] Record the prior 89.30% dirty-tile result only inside its validated test boundary.

## 123. PDC Startup, Service, and Runtime Lanes

- [ ] Model service dependency graph.
- [ ] Observe historical startup durations.
- [ ] Observe hardware readiness.
- [ ] Observe storage contention.
- [ ] Observe CPU contention.
- [ ] Observe network dependency.
- [ ] Preserve hard ordering constraints.
- [ ] Preserve security initialization order.
- [ ] Parallelize only independent services.
- [ ] Delay optional services only within user-experience budgets.
- [ ] Never delay security updates, authentication, logging, or recovery services beyond defined limits.
- [ ] Verify final service state.
- [ ] Measure boot from firmware handoff to usable session.
- [ ] Separate cold and warm storage effects.
- [ ] Implement application runtime API for explicit opt-in optimization.
- [ ] Version runtime contracts.
- [ ] Verify output equivalence.
- [ ] Account runtime setup cost.

## 124. PooleGlyph Language and System Policy

### 124.1 Language specification

- [ ] Publish lexical grammar.
- [ ] Publish token set.
- [ ] Publish Unicode identifier policy.
- [ ] Publish comments syntax.
- [ ] Publish literal syntax.
- [ ] Publish operator syntax.
- [ ] Publish precedence.
- [ ] Publish declaration syntax.
- [ ] Publish type system.
- [ ] Publish module system.
- [ ] Publish import resolution.
- [ ] Publish visibility rules.
- [ ] Publish generics policy if any.
- [ ] Publish error semantics.
- [ ] Publish versioning rules.
- [ ] Publish capability semantics.
- [ ] Publish resource semantics.
- [ ] Publish permission semantics.
- [ ] Publish lifecycle semantics.
- [ ] Publish service semantics.
- [ ] Publish package semantics.
- [ ] Publish deployment semantics.
- [ ] Publish policy semantics.
- [ ] Publish contract semantics.
- [ ] Publish interface, adapter, binding, route, channel, endpoint, port, and gateway semantics.

### 124.2 Front end

- [ ] Implement source loader.
- [ ] Implement UTF-8 validation.
- [ ] Implement lexer.
- [ ] Implement parser.
- [ ] Implement error recovery.
- [ ] Implement source spans.
- [ ] Implement abstract syntax tree.
- [ ] Implement name resolution.
- [ ] Implement module resolution.
- [ ] Implement type checking.
- [ ] Implement constant evaluation.
- [ ] Implement permission checking.
- [ ] Implement capability checking.
- [ ] Implement cycle detection.
- [ ] Implement linter.
- [ ] Implement formatter.
- [ ] Implement syntax highlighter.
- [ ] Implement language server.
- [ ] Fuzz lexer and parser.
- [ ] Fuzz type checker.
- [ ] Create parser differential tests from grammar.

### 124.3 Intermediate representation and compiler

- [ ] Define CoreIR schema.
- [ ] Version CoreIR.
- [ ] Define canonical serialization.
- [ ] Define deterministic ordering.
- [ ] Lower AST to CoreIR.
- [ ] Validate CoreIR independently.
- [ ] Define policy IR.
- [ ] Define service graph IR.
- [ ] Define permission IR.
- [ ] Define resource IR.
- [ ] Define deployment IR.
- [ ] Generate kernel policy artifacts.
- [ ] Generate service manager manifests.
- [ ] Generate package metadata.
- [ ] Generate PDC policy bundles.
- [ ] Generate human-readable explanations.
- [ ] Generate hashes.
- [ ] Sign production policy bundles.
- [ ] Prevent compiler nondeterminism.
- [ ] Create round-trip and golden tests.

### 124.4 Runtime and policy engine

- [ ] Load only version-compatible compiled policies.
- [ ] Verify signatures.
- [ ] Verify hashes.
- [ ] Validate resource references.
- [ ] Validate capability grants.
- [ ] Validate dependency graph.
- [ ] Validate lifecycle transitions.
- [ ] Validate rollback definitions.
- [ ] Validate timeouts.
- [ ] Validate default-deny behavior.
- [ ] Apply policy transactionally.
- [ ] Record policy activation.
- [ ] Support policy rollback.
- [ ] Keep last known-good policy.
- [ ] Boot safe mode without optional policy.
- [ ] Prevent policy from expressing arbitrary kernel memory or register access.
- [ ] Prevent policy from invoking arbitrary shell commands as root.
- [ ] Sandbox policy evaluation.
- [ ] Bound policy execution time and memory.

### 124.5 Developer tooling

- [ ] Create PooleGlyph compiler CLI.
- [ ] Create formatter CLI.
- [ ] Create linter CLI.
- [ ] Create package CLI.
- [ ] Create dependency graph viewer.
- [ ] Create permission explainer.
- [ ] Create policy simulator.
- [ ] Create policy diff tool.
- [ ] Create migration tool.
- [ ] Create debugger.
- [ ] Create trace viewer.
- [ ] Create test framework.
- [ ] Create documentation generator.
- [ ] Create examples repository.
- [ ] Create standard library.
- [ ] Create compatibility checker.
- [ ] Create signed package publisher.

## 125. Reliability, Watchdogs, and Fault Containment

- [ ] Implement hardware watchdog support only for a documented target watchdog.
- [ ] Implement software scheduler watchdog.
- [ ] Implement per-service watchdog.
- [ ] Implement storage completion watchdog.
- [ ] Implement GPU hang watchdog.
- [ ] Implement network firmware watchdog.
- [ ] Implement PDC watchdog.
- [ ] Define watchdog ownership.
- [ ] Define heartbeat interval.
- [ ] Define timeout.
- [ ] Define escalation levels.
- [ ] Attempt local component reset first.
- [ ] Restart user-space service when safe.
- [ ] Reset device when safe.
- [ ] Disable faulty driver when safe.
- [ ] Roll back PDC action when applicable.
- [ ] Enter degraded mode.
- [ ] Reboot to safe mode only when local recovery fails.
- [ ] Prevent reboot loops.
- [ ] Persist failure reason.
- [ ] Count repeated failures.
- [ ] Quarantine repeatedly failing components.
- [ ] Expose degraded status to user.
- [ ] Test watchdog itself for hangs and false positives.

## 126. Virtualization and Optional Hypervisor Support

- [ ] Decide whether AMD SVM support is in scope.
- [ ] Discover virtualization capabilities.
- [ ] Enable virtualization per CPU.
- [ ] Allocate VMCB structures.
- [ ] Define guest physical memory.
- [ ] Define nested page tables.
- [ ] Handle VM exits.
- [ ] Emulate required instructions and devices.
- [ ] Implement virtual interrupt injection.
- [ ] Implement virtual timers.
- [ ] Implement virtual storage.
- [ ] Implement virtual network.
- [ ] Implement snapshot only with state-consistency guarantees.
- [ ] Isolate guests with IOMMU if device assignment is added.
- [ ] Prevent guest escape.
- [ ] Fuzz hypercall and device emulation interfaces.
- [ ] Keep hypervisor support out of trusted base until audited if not essential.

## 127. Hardware Error Reporting and Resilience

- [ ] Initialize machine-check architecture.
- [ ] Enumerate machine-check banks.
- [ ] Enable corrected-error reporting conservatively.
- [ ] Handle corrected errors.
- [ ] Handle deferred errors.
- [ ] Handle uncorrected recoverable errors if architecture permits.
- [ ] Handle fatal errors.
- [ ] Capture syndrome and address information.
- [ ] Map errors to CPU, memory, or device when possible.
- [ ] Integrate ACPI HEST when supported.
- [ ] Integrate APEI error records when supported.
- [ ] Integrate PCIe AER.
- [ ] Integrate NVMe health warnings.
- [ ] Integrate memory ECC reports if exposed.
- [ ] Rate-limit repeated correctable errors.
- [ ] Retire bad pages if safely identifiable.
- [ ] Quarantine failing devices.
- [ ] Warn user of impending storage failure.
- [ ] Preserve error records across reboot.
- [ ] Do not continue after integrity cannot be assured.

## 128. Test Architecture

### 128.1 Unit tests

- [ ] Create host-runnable tests for pure algorithms.
- [ ] Create kernel in-situ unit-test framework.
- [ ] Create user-space unit-test framework.
- [ ] Test parsers with valid vectors.
- [ ] Test parsers with invalid vectors.
- [ ] Test allocators.
- [ ] Test data structures.
- [ ] Test arithmetic boundaries.
- [ ] Test serialization.
- [ ] Test ABI structures.
- [ ] Test policy rules.
- [ ] Test filesystem metadata operations.
- [ ] Test networking checksums.
- [ ] Test cryptographic vectors.
- [ ] Test time conversions.
- [ ] Test Unicode handling.
- [ ] Test PooleGlyph front end.
- [ ] Test PDC receipt verification.
- [ ] Run tests deterministically.
- [ ] Record random seeds for randomized tests.

### 128.2 Integration tests

- [ ] Test bootloader-to-kernel handoff.
- [ ] Test kernel-to-init handoff.
- [ ] Test process creation and exec.
- [ ] Test dynamic linking.
- [ ] Test service startup and supervision.
- [ ] Test device discovery and driver binding.
- [ ] Test storage through filesystem.
- [ ] Test USB through input event.
- [ ] Test network through DNS and TLS.
- [ ] Test display through compositor presentation.
- [ ] Test audio through playback and capture loopback where possible.
- [ ] Test package install and removal.
- [ ] Test update and rollback.
- [ ] Test installer and first boot.
- [ ] Test recovery environment.
- [ ] Test PDC proposal, rejection, actuation, verification, and rollback.

### 128.3 System and acceptance tests

- [ ] Test cold boot.
- [ ] Test warm reboot.
- [ ] Test repeated reboot.
- [ ] Test shutdown.
- [ ] Test boot with one CPU.
- [ ] Test boot with all CPUs.
- [ ] Test minimum RAM.
- [ ] Test large RAM.
- [ ] Test empty user-data volume.
- [ ] Test nearly full volume.
- [ ] Test full volume.
- [ ] Test missing network.
- [ ] Test missing optional devices.
- [ ] Test device disconnect.
- [ ] Test malformed removable media.
- [ ] Test invalid update.
- [ ] Test revoked signature.
- [ ] Test failed service.
- [ ] Test failed driver.
- [ ] Test PDC-disabled safe mode.
- [ ] Test previous-known-good boot.
- [ ] Test recovery from corrupted configuration.
- [ ] Test 24-hour, 72-hour, and longer stability runs.

## 129. Fuzzing

- [ ] Fuzz UEFI boot configuration parser.
- [ ] Fuzz ELF loader.
- [ ] Fuzz boot protocol parser.
- [ ] Fuzz ACPI table parsers.
- [ ] Fuzz AML parser and evaluator.
- [ ] Fuzz SMBIOS parser.
- [ ] Fuzz PCI capability parser.
- [ ] Fuzz USB descriptors.
- [ ] Fuzz HID report descriptors.
- [ ] Fuzz USB mass-storage responses.
- [ ] Fuzz filesystem images.
- [ ] Fuzz partition tables.
- [ ] Fuzz package files.
- [ ] Fuzz update metadata.
- [ ] Fuzz network frames.
- [ ] Fuzz ARP.
- [ ] Fuzz IPv4 and IPv6.
- [ ] Fuzz ICMP.
- [ ] Fuzz UDP and TCP options.
- [ ] Fuzz DNS.
- [ ] Fuzz DHCP.
- [ ] Fuzz Wi-Fi management frames.
- [ ] Fuzz Bluetooth protocols.
- [ ] Fuzz TLS and certificate parsing.
- [ ] Fuzz image formats.
- [ ] Fuzz font formats.
- [ ] Fuzz audio and media formats.
- [ ] Fuzz compositor protocol.
- [ ] Fuzz system calls.
- [ ] Fuzz driver control interfaces.
- [ ] Fuzz PooleGlyph source and compiled policy.
- [ ] Fuzz PDC proposals and receipts.
- [ ] Maintain seed corpora.
- [ ] Minimize crashing inputs.
- [ ] Deduplicate crashes.
- [ ] Run fuzzers with sanitizers on host-portable code.
- [ ] Run kernel fuzzing in disposable virtual machines.

## 130. Fault Injection

- [ ] Inject allocation failure at every allocation site.
- [ ] Inject page-table allocation failure.
- [ ] Inject thread creation failure.
- [ ] Inject lock timeout where supported.
- [ ] Inject timer delay.
- [ ] Inject lost interrupt.
- [ ] Inject duplicate interrupt.
- [ ] Inject interrupt storm.
- [ ] Inject DMA mapping failure.
- [ ] Inject IOMMU fault.
- [ ] Inject PCI read failure where emulation permits.
- [ ] Inject USB disconnect during transfer.
- [ ] Inject USB stall.
- [ ] Inject NVMe timeout.
- [ ] Inject NVMe reset.
- [ ] Inject block read error.
- [ ] Inject block write error.
- [ ] Inject flush failure.
- [ ] Inject disk full.
- [ ] Inject filesystem checksum failure.
- [ ] Inject network loss.
- [ ] Inject packet corruption.
- [ ] Inject packet reordering.
- [ ] Inject DNS failure.
- [ ] Inject clock jump.
- [ ] Inject RTC invalid state.
- [ ] Inject service crash.
- [ ] Inject service hang.
- [ ] Inject updater interruption.
- [ ] Inject power loss during update.
- [ ] Inject panic during crash dump.
- [ ] Inject PDC observer loss.
- [ ] Inject PDC planner crash.
- [ ] Inject PDC actuator crash.
- [ ] Inject PDC watchdog trigger.
- [ ] Verify bounded and documented recovery from every injection.

## 131. Storage Power-Loss and Corruption Testing

- [ ] Use sacrificial hardware.
- [ ] Automate abrupt power removal.
- [ ] Record exact operation at cut point.
- [ ] Cut power during file create.
- [ ] Cut power during file write.
- [ ] Cut power during append.
- [ ] Cut power during truncate.
- [ ] Cut power during rename.
- [ ] Cut power during unlink.
- [ ] Cut power during directory update.
- [ ] Cut power during fsync.
- [ ] Cut power during package transaction.
- [ ] Cut power during update slot write.
- [ ] Cut power during boot-state update.
- [ ] Cut power during filesystem repair.
- [ ] Repeat across randomized cut points.
- [ ] Verify mount behavior.
- [ ] Verify journal replay.
- [ ] Verify user-visible data guarantees.
- [ ] Verify no cross-file data exposure.
- [ ] Verify filesystem checker consistency.
- [ ] Retain failing disk images.
- [ ] Retain device health logs.

## 132. Security Testing

- [ ] Run static security analysis.
- [ ] Run dependency vulnerability scans.
- [ ] Run SBOM vulnerability correlation.
- [ ] Run privilege-boundary tests.
- [ ] Run authentication bypass tests.
- [ ] Run permission matrix tests.
- [ ] Run sandbox escape tests.
- [ ] Run malformed package tests.
- [ ] Run malicious update tests.
- [ ] Run boot-chain tampering tests.
- [ ] Run rollback attack tests.
- [ ] Run stolen-key response drill.
- [ ] Run DMA attack tests where hardware permits.
- [ ] Run malicious USB tests.
- [ ] Run hostile network tests.
- [ ] Run hostile Wi-Fi access-point tests.
- [ ] Run hostile Bluetooth peer tests.
- [ ] Run filesystem race tests.
- [ ] Run TOCTOU tests.
- [ ] Run symlink attack tests.
- [ ] Run secret-leak tests.
- [ ] Run crash-dump redaction tests.
- [ ] Run log redaction tests.
- [ ] Run secure-deletion expectation tests.
- [ ] Commission external review before production claims.

## 133. Compatibility and Conformance Testing

- [ ] Test UEFI boot on OVMF.
- [ ] Test UEFI boot on target firmware.
- [ ] Test ACPI tables from target firmware revisions.
- [ ] Test SMBIOS variations.
- [ ] Test exact CPU stepping.
- [ ] Test exact GPU VBIOS.
- [ ] Test exact storage firmware.
- [ ] Test exact NIC firmware.
- [ ] Test exact Wi-Fi firmware.
- [ ] Test exact monitor EDID.
- [ ] Test multiple keyboards and mice.
- [ ] Test USB hubs.
- [ ] Test removable drives.
- [ ] Test network interoperability with independent systems.
- [ ] Test TCP interoperability.
- [ ] Test IPv6 interoperability.
- [ ] Test DNS interoperability.
- [ ] Test TLS interoperability.
- [ ] Test Bluetooth profile interoperability.
- [ ] Test POSIX interfaces against conformance suites.
- [ ] Test Vulkan or OpenGL only through official conformance process before claims.
- [ ] Test package upgrade from every supported release.
- [ ] Publish compatibility results by exact hardware identifier.

## 134. Performance and Regression Testing

- [ ] Create boot-time benchmark.
- [ ] Create shutdown-time benchmark.
- [ ] Create process-spawn benchmark.
- [ ] Create context-switch benchmark.
- [ ] Create syscall benchmark.
- [ ] Create scheduler latency benchmark.
- [ ] Create memory allocation benchmark.
- [ ] Create page-fault benchmark.
- [ ] Create file read and write benchmarks.
- [ ] Create fsync latency benchmark.
- [ ] Create storage queue benchmark.
- [ ] Create network latency benchmark.
- [ ] Create network throughput benchmark.
- [ ] Create DNS lookup benchmark.
- [ ] Create TLS handshake benchmark.
- [ ] Create compositor frame benchmark.
- [ ] Create dirty-region composition benchmark.
- [ ] Create input latency benchmark.
- [ ] Create audio round-trip benchmark.
- [ ] Create idle power benchmark.
- [ ] Create sustained thermal benchmark.
- [ ] Create package transaction benchmark.
- [ ] Create update benchmark.
- [ ] Create PDC overhead benchmark.
- [ ] Set regression thresholds.
- [ ] Require correctness checks in every benchmark.
- [ ] Preserve benchmark environment manifests.
- [ ] Separate microbenchmarks from user-visible outcomes.

## 135. Reproducible Builds, SBOM, and Supply-Chain Provenance

- [ ] Make release builds hermetic.
- [ ] Pin source revisions.
- [ ] Pin toolchain versions.
- [ ] Pin build-container or VM image.
- [ ] Pin dependency archives by hash.
- [ ] Disable undeclared network access.
- [ ] Normalize timestamps.
- [ ] Normalize path prefixes.
- [ ] Normalize locales.
- [ ] Normalize archive order.
- [ ] Normalize filesystem image metadata.
- [ ] Generate deterministic package ordering.
- [ ] Generate bit-identical artifacts on independent builders.
- [ ] Investigate every nonreproducible byte.
- [ ] Generate SPDX 3.0 or selected supported SBOM format.
- [ ] List source packages.
- [ ] List binary packages.
- [ ] List firmware blobs.
- [ ] List licenses.
- [ ] List hashes.
- [ ] List dependency relationships.
- [ ] Generate SLSA-compatible provenance.
- [ ] Sign provenance.
- [ ] Publish verification instructions.
- [ ] Archive build logs.
- [ ] Archive source snapshots.
- [ ] Archive toolchain binaries or reproducible recipes.

## 136. Release Engineering

### 136.1 Versioning and channels

- [ ] Define semantic or project-specific version scheme.
- [ ] Version bootloader independently.
- [ ] Version kernel independently.
- [ ] Version user ABI independently.
- [ ] Version driver ABI independently.
- [ ] Version package format independently.
- [ ] Version filesystem format independently.
- [ ] Version PooleGlyph independently.
- [ ] Version PDC receipt schema independently.
- [ ] Define development channel.
- [ ] Define nightly channel.
- [ ] Define alpha channel.
- [ ] Define beta channel.
- [ ] Define stable channel.
- [ ] Define long-term support policy if any.
- [ ] Define compatibility window.
- [ ] Define deprecation window.

### 136.2 Release candidate gates

- [ ] Freeze source revisions.
- [ ] Freeze specification versions.
- [ ] Freeze package repository snapshot.
- [ ] Build on clean builders.
- [ ] Verify reproducibility.
- [ ] Run full emulator suite.
- [ ] Run full hardware suite.
- [ ] Run installer suite.
- [ ] Run update suite.
- [ ] Run rollback suite.
- [ ] Run recovery suite.
- [ ] Run storage power-loss suite.
- [ ] Run security suite.
- [ ] Run performance-regression suite.
- [ ] Run long-duration stability suite.
- [ ] Review known issues.
- [ ] Review unchecked security-critical checklist items.
- [ ] Review license manifest.
- [ ] Review SBOM.
- [ ] Review signing keys and ceremony.
- [ ] Create release notes.
- [ ] Create migration notes.
- [ ] Create recovery notes.
- [ ] Obtain release approval.

### 136.3 Release artifacts

- [ ] Publish bootable disk image.
- [ ] Publish recovery image.
- [ ] Publish installer image.
- [ ] Publish source archives.
- [ ] Publish source commit hashes.
- [ ] Publish package repository snapshot.
- [ ] Publish checksums.
- [ ] Publish signatures.
- [ ] Publish public signing keys.
- [ ] Publish SBOM.
- [ ] Publish provenance.
- [ ] Publish build instructions.
- [ ] Publish reproducibility instructions.
- [ ] Publish hardware support matrix.
- [ ] Publish known issues.
- [ ] Publish benchmark methodology.
- [ ] Publish benchmark receipts.
- [ ] Publish security contact.
- [ ] Publish privacy statement.

## 137. Signing Keys and Release Ceremony

- [ ] Generate root key offline.
- [ ] Use hardware security module or offline encrypted storage where practical.
- [ ] Create multiple verified backups.
- [ ] Use split custody if team size permits.
- [ ] Document key fingerprints offline.
- [ ] Create intermediate release keys.
- [ ] Create package repository keys.
- [ ] Create update metadata keys.
- [ ] Create boot image keys.
- [ ] Separate development keys.
- [ ] Set expirations.
- [ ] Define rotation schedule.
- [ ] Define revocation artifacts.
- [ ] Test revocation before release.
- [ ] Record signing ceremony.
- [ ] Verify artifacts on an independent machine before publication.
- [ ] Never store production private keys in CI plaintext.
- [ ] Audit signing access.

## 138. Operations, Support, and Incident Response

- [ ] Create issue-report template.
- [ ] Create crash-report template.
- [ ] Create hardware compatibility report template.
- [ ] Create security advisory format.
- [ ] Create severity classification.
- [ ] Create triage process.
- [ ] Create regression bisection process.
- [ ] Create release rollback process.
- [ ] Create emergency update process.
- [ ] Create compromised-key response plan.
- [ ] Create compromised-mirror response plan.
- [ ] Create malicious-package response plan.
- [ ] Create filesystem-corruption response plan.
- [ ] Create data-loss incident process.
- [ ] Create privacy incident process.
- [ ] Create service-status page only if network services exist.
- [ ] Create end-of-life policy.
- [ ] Create support-window policy.
- [ ] Maintain known-issues database.
- [ ] Maintain workarounds database.
- [ ] Publish postmortems for severe incidents.

## 139. Documentation Set

- [ ] Write project overview.
- [ ] Write architecture overview.
- [ ] Write boot architecture.
- [ ] Write kernel architecture.
- [ ] Write memory-management design.
- [ ] Write scheduler design.
- [ ] Write process and syscall ABI specification.
- [ ] Write driver model specification.
- [ ] Write ACPI implementation notes.
- [ ] Write PCI and DMA design.
- [ ] Write storage architecture.
- [ ] Write filesystem format specification.
- [ ] Write network architecture.
- [ ] Write graphics architecture.
- [ ] Write audio architecture.
- [ ] Write security architecture.
- [ ] Write threat model.
- [ ] Write package format specification.
- [ ] Write update format specification.
- [ ] Write recovery manual.
- [ ] Write installer manual.
- [ ] Write developer setup guide.
- [ ] Write build guide.
- [ ] Write debugging guide.
- [ ] Write testing guide.
- [ ] Write driver porting guide.
- [ ] Write application porting guide.
- [ ] Write SDK guide.
- [ ] Write PooleGlyph specification.
- [ ] Write PDC architecture and claim policy.
- [ ] Write benchmark methodology.
- [ ] Write release process.
- [ ] Write vulnerability response policy.
- [ ] Write hardware support matrix.
- [ ] Write user guide.
- [ ] Write accessibility guide.
- [ ] Keep docs versioned with source.
- [ ] Test every command in documentation.

## 140. Universal Definition of Done for Every Component

- [ ] Write component requirements.
- [ ] Write component threat model.
- [ ] Write component API or protocol specification.
- [ ] Write component state machine.
- [ ] Write component ownership and lifetime rules.
- [ ] Write component concurrency rules.
- [ ] Write component error taxonomy.
- [ ] Write component timeout behavior.
- [ ] Write component cancellation behavior.
- [ ] Write component resource limits.
- [ ] Write component security boundaries.
- [ ] Write component observability fields.
- [ ] Write component versioning policy.
- [ ] Implement normal path.
- [ ] Implement all documented error paths.
- [ ] Implement teardown path.
- [ ] Implement reset path when applicable.
- [ ] Implement suspend and resume when applicable.
- [ ] Implement hotplug when applicable.
- [ ] Implement rollback when applicable.
- [ ] Add unit tests.
- [ ] Add integration tests.
- [ ] Add malformed-input tests.
- [ ] Add concurrency tests.
- [ ] Add resource-exhaustion tests.
- [ ] Add fault-injection tests.
- [ ] Add performance tests.
- [ ] Add long-duration tests.
- [ ] Add fuzz target for untrusted inputs.
- [ ] Add structured logs.
- [ ] Add metrics.
- [ ] Add tracepoints.
- [ ] Add debugging tools.
- [ ] Add user documentation.
- [ ] Add developer documentation.
- [ ] Add recovery documentation.
- [ ] Add license metadata.
- [ ] Add SBOM metadata.
- [ ] Add compatibility records.
- [ ] Add release gate.
- [ ] Obtain independent review for security-critical code.

## 141. Boot-Order and System-Process Dependency Checklist

- [ ] Firmware initializes platform and selects PooleOS boot entry.
- [ ] Bootloader verifies its own trust state.
- [ ] Bootloader verifies kernel, initramfs, modules, and policy artifacts.
- [ ] Bootloader obtains final memory map and exits boot services.
- [ ] Kernel establishes architecture, memory, exceptions, interrupts, timers, and CPUs.
- [ ] Kernel initializes device model and firmware interfaces.
- [ ] Kernel initializes storage required for initial root.
- [ ] Kernel mounts initramfs.
- [ ] Kernel starts PID 1.
- [ ] PID 1 mounts pseudo filesystems.
- [ ] PID 1 initializes logging.
- [ ] PID 1 initializes device manager.
- [ ] Device manager performs cold-plug enumeration.
- [ ] Firmware loader satisfies driver firmware requests.
- [ ] Storage drivers expose root device.
- [ ] Mount manager validates and mounts persistent root.
- [ ] PID 1 pivots to persistent root.
- [ ] PID 1 starts entropy seed service.
- [ ] PID 1 starts hardware error and watchdog services.
- [ ] PID 1 starts time initialization and synchronization.
- [ ] PID 1 starts network manager and required protocol clients.
- [ ] PID 1 starts authentication and privilege services.
- [ ] PID 1 starts package and update services.
- [ ] PID 1 starts PDC observer and watchdog in non-actuating mode.
- [ ] PID 1 starts login manager.
- [ ] Login manager authenticates user.
- [ ] Session manager starts per-user services.
- [ ] Display manager starts compositor.
- [ ] Compositor acquires display and input devices.
- [ ] Audio server acquires audio devices.
- [ ] Desktop shell starts.
- [ ] PDC UI connects as an unprivileged client.
- [ ] PDC actuator remains disabled until policy, watchdog, rollback, and user mode allow it.
- [ ] System marks boot successful only after required health gates pass.
- [ ] Shutdown reverses dependencies and persists success or failure state.

## 142. Dependency-Ordered Milestone Roadmap

### 142.0 Milestone 0 — Project and toolchain

- [ ] Freeze initial from-scratch definition.
- [ ] Freeze x86-64 UEFI target.
- [ ] Inventory exact hardware.
- [ ] Create repositories.
- [ ] Create build system.
- [ ] Create cross compiler and sysroot.
- [ ] Create QEMU and OVMF launch scripts.
- [ ] Create CI debug build.
- [ ] Create source and license policy.
- [ ] Create architecture decision records.
- [ ] Pass reproducible host-tool bootstrap.

### 142.1 Milestone 1 — UEFI proof of life

- [ ] Build PE32+ EFI application.
- [ ] Print to UEFI console.
- [ ] Print to serial if available.
- [ ] Open the EFI System Partition.
- [ ] Load a file.
- [ ] Enumerate GOP modes.
- [ ] Render to framebuffer.
- [ ] Read ACPI and SMBIOS pointers.
- [ ] Retrieve memory map.
- [ ] Exit boot services successfully.
- [ ] Halt predictably.
- [ ] Boot in OVMF and target firmware.

### 142.2 Milestone 2 — Kernel proof of life

- [ ] Load ELF kernel.
- [ ] Enter kernel.
- [ ] Validate boot handoff.
- [ ] Initialize early console.
- [ ] Initialize GDT, IDT, and TSS.
- [ ] Handle deliberate breakpoint.
- [ ] Handle deliberate page fault.
- [ ] Initialize basic page tables.
- [ ] Initialize physical allocator.
- [ ] Initialize kernel heap.
- [ ] Panic with stack and register dump.
- [ ] Pass repeated QEMU boots.

### 142.3 Milestone 3 — Interrupts, timers, and SMP

- [ ] Parse MADT.
- [ ] Enable local APIC.
- [ ] Configure I/O APIC.
- [ ] Handle timer interrupts.
- [ ] Implement monotonic clock.
- [ ] Start all target CPU threads.
- [ ] Send inter-processor interrupts.
- [ ] Implement locks.
- [ ] Implement per-CPU data.
- [ ] Implement basic scheduler.
- [ ] Run kernel threads on multiple CPUs.
- [ ] Pass SMP stress tests.

### 142.4 Milestone 4 — User mode

- [ ] Define syscall ABI.
- [ ] Enter ring 3.
- [ ] Return through system call.
- [ ] Create process address space.
- [ ] Load static ELF executable.
- [ ] Implement process exit and wait.
- [ ] Implement user memory copying.
- [ ] Implement signals or exception delivery minimum.
- [ ] Implement pipes and basic IPC.
- [ ] Start first user-space init from initramfs.
- [ ] Run shell-like test process.

### 142.5 Milestone 5 — Device and storage foundation

- [ ] Parse ACPI tables.
- [ ] Enumerate PCIe.
- [ ] Enable MSI or MSI-X.
- [ ] Implement DMA API.
- [ ] Implement IOMMU for target platform.
- [ ] Implement NVMe admin queue.
- [ ] Identify namespace.
- [ ] Read blocks.
- [ ] Write blocks on sacrificial disk.
- [ ] Flush correctly.
- [ ] Parse GPT.
- [ ] Mount FAT32 read-only.
- [ ] Mount initramfs and memory filesystems.
- [ ] Pass storage error-injection tests.

### 142.6 Milestone 6 — Native root filesystem

- [ ] Implement VFS.
- [ ] Implement path lookup.
- [ ] Implement file descriptors.
- [ ] Implement page cache.
- [ ] Implement first writable filesystem.
- [ ] Implement crash-consistency mechanism.
- [ ] Implement filesystem checker.
- [ ] Install and boot from persistent root on spare SSD.
- [ ] Pass randomized power-cut tests.
- [ ] Recover to known state after corruption.

### 142.7 Milestone 7 — USB input

- [ ] Initialize xHCI.
- [ ] Enumerate root ports.
- [ ] Enumerate a USB keyboard.
- [ ] Enumerate a USB mouse.
- [ ] Parse HID reports.
- [ ] Feed input subsystem.
- [ ] Drive serial or framebuffer console interactively.
- [ ] Support a basic USB hub.
- [ ] Handle disconnect and reconnect.
- [ ] Pass malformed-descriptor tests.

### 142.8 Milestone 8 — Core userland

- [ ] Implement process runtime.
- [ ] Implement basic libc.
- [ ] Implement malloc.
- [ ] Implement standard I/O.
- [ ] Implement thread library minimum.
- [ ] Implement shell.
- [ ] Implement essential utilities.
- [ ] Implement init and service manager.
- [ ] Implement structured logging.
- [ ] Implement account and login system.
- [ ] Implement package format minimum.

### 142.9 Milestone 9 — Ethernet and Internet

- [ ] Implement target Ethernet driver.
- [ ] Implement Ethernet framing.
- [ ] Implement ARP.
- [ ] Implement IPv4.
- [ ] Implement ICMP.
- [ ] Implement UDP.
- [ ] Implement TCP.
- [ ] Implement DHCPv4.
- [ ] Implement DNS resolver.
- [ ] Implement IPv6 core and neighbor discovery.
- [ ] Implement TLS through reviewed cryptographic stack.
- [ ] Fetch a signed package over the network.
- [ ] Pass hostile packet fuzzing.

### 142.10 Milestone 10 — Software desktop

- [ ] Use GOP framebuffer.
- [ ] Implement software renderer.
- [ ] Implement font rendering.
- [ ] Implement compositor protocol.
- [ ] Implement compositor.
- [ ] Implement window management.
- [ ] Implement keyboard and pointer dispatch.
- [ ] Implement terminal emulator.
- [ ] Implement settings and basic desktop shell.
- [ ] Run multiple graphical clients without accelerated GPU.

### 142.11 Milestone 11 — Audio, Wi-Fi, and Bluetooth

- [ ] Implement HDA target controller and codec.
- [ ] Implement audio server.
- [ ] Implement target Wi-Fi transport and firmware.
- [ ] Implement scan, WPA2/WPA3, association, and data path.
- [ ] Implement network manager integration.
- [ ] Implement Bluetooth HCI.
- [ ] Implement HID over Bluetooth.
- [ ] Implement Bluetooth audio only after core stability.
- [ ] Pass radio regulatory and security tests.

### 142.12 Milestone 12 — Secure installation and updates

- [ ] Implement Secure Boot signing.
- [ ] Implement measured boot.
- [ ] Implement TPM integration.
- [ ] Implement signed packages.
- [ ] Implement atomic system images.
- [ ] Implement automatic rollback.
- [ ] Implement recovery environment.
- [ ] Implement installer.
- [ ] Implement key rotation and revocation.
- [ ] Pass malicious update and rollback-attack tests.

### 142.13 Milestone 13 — PDC observation and receipts

- [ ] Implement observer-only services.
- [ ] Implement system topology model.
- [ ] Implement planner in proposal-only mode.
- [ ] Implement policy validator.
- [ ] Implement signed receipts.
- [ ] Implement independent verifier.
- [ ] Establish baseline and neutral control routes.
- [ ] Measure observer and planner overhead.
- [ ] Publish no automatic actuation yet.

### 142.14 Milestone 14 — First bounded PDC actuator

- [ ] Choose one low-risk reversible action.
- [ ] Define exact claim boundary.
- [ ] Implement capability-separated actuator.
- [ ] Implement watchdog.
- [ ] Implement rollback.
- [ ] Implement failure injection.
- [ ] Run adversarial tests.
- [ ] Run repeated baseline/control/PDC trials.
- [ ] Require correctness equivalence.
- [ ] Promote only the validated workload family.

### 142.15 Milestone 15 — Native accelerated graphics research

- [ ] Retain permanent GOP safe mode.
- [ ] Complete lawful documentation and firmware prerequisites.
- [ ] Bring up one connector and one display mode.
- [ ] Implement scanout.
- [ ] Implement vblank and page flip.
- [ ] Implement GPU memory management.
- [ ] Implement copy engine.
- [ ] Implement isolated command submission.
- [ ] Implement reset and hang recovery.
- [ ] Implement user-space graphics API.
- [ ] Pass reference-render and conformance comparisons.
- [ ] Do not make accelerated graphics a dependency of recovery.

## 143. First Hardware Boot Acceptance Checklist

- [ ] Confirm target disk is a spare disk.
- [ ] Confirm full backup exists.
- [ ] Confirm recovery USB boots.
- [ ] Confirm current firmware settings are recorded.
- [ ] Confirm test image hash.
- [ ] Confirm bootloader signature state.
- [ ] Confirm PDC is disabled.
- [ ] Confirm native GPU driver is disabled.
- [ ] Confirm write support is disabled unless explicitly being tested.
- [ ] Confirm serial or second-machine observation path.
- [ ] Boot through firmware menu.
- [ ] Capture bootloader log.
- [ ] Capture final UEFI memory map.
- [ ] Capture kernel entry log.
- [ ] Capture CPU feature report.
- [ ] Capture ACPI and SMBIOS hashes.
- [ ] Capture PCI inventory.
- [ ] Capture timer calibration.
- [ ] Capture SMP startup status.
- [ ] Capture memory allocator self-test.
- [ ] Capture interrupt self-test.
- [ ] Capture clean halt or reboot.
- [ ] Compare observed hardware against inventory.
- [ ] Record any firmware anomalies.
- [ ] Do not proceed to destructive storage until repeatable read-only boots pass.

## 144. Daily-Driver Readiness Gate

- [ ] No unresolved kernel memory-corruption defects.
- [ ] No unresolved filesystem data-loss defects.
- [ ] No unresolved update rollback defects.
- [ ] No unresolved privilege-escalation defects.
- [ ] No unresolved boot-loop defects.
- [ ] Recovery media verified on target hardware.
- [ ] Previous-known-good boot verified.
- [ ] PDC-disabled safe mode verified.
- [ ] Persistent root survives repeated abrupt power tests within documented guarantees.
- [ ] Installer cannot silently target the wrong disk.
- [ ] Package and update signatures verified.
- [ ] Authentication and screen lock verified.
- [ ] Network firewall defaults verified.
- [ ] TLS and root certificate updates verified.
- [ ] USB input stable.
- [ ] Display stable.
- [ ] Audio stable.
- [ ] Ethernet or Wi-Fi stable.
- [ ] Time synchronization stable.
- [ ] Logs and crash dumps usable.
- [ ] Idle thermal and power behavior safe.
- [ ] Sustained-load thermal behavior safe.
- [ ] 72-hour mixed workload run passes.
- [ ] Known limitations published.
- [ ] User data backup and restore tested.

## 145. Public Alpha Readiness Gate

- [ ] Source repository publicly reviewable or disclosure model documented.
- [ ] License obligations complete.
- [ ] Third-party notices complete.
- [ ] Firmware redistribution rights complete.
- [ ] Reproducible build verified independently.
- [ ] SBOM published.
- [ ] Provenance published.
- [ ] Signed release image published.
- [ ] Public signing key verified through multiple channels.
- [ ] Hardware support matrix published.
- [ ] Exact recovery procedure published.
- [ ] Exact uninstall or disk-removal procedure published.
- [ ] Security contact active.
- [ ] Vulnerability response process active.
- [ ] Privacy policy published.
- [ ] Telemetry disabled by default or clearly consented.
- [ ] Crash reporting opt-in.
- [ ] Known high-risk limitations highlighted.
- [ ] Performance claims include receipts and boundaries.
- [ ] No unverified machine-wide optimization claims.
- [ ] Release has been installed, updated, rolled back, and recovered on target hardware.

## 146. Primary Standards and Official Reference Register

### 146.1 Firmware and platform

- [ ] Review the UEFI Forum specifications index: https://uefi.org/specifications
- [ ] Review UEFI Specification 2.11 or the current superseding revision: https://uefi.org/specs/UEFI/2.11/
- [ ] Review UEFI Boot Manager requirements: https://uefi.org/specs/UEFI/2.11/03_Boot_Manager.html
- [ ] Review UEFI Secure Boot and Driver Signing: https://uefi.org/specs/UEFI/2.11/32_Secure_Boot_and_Driver_Signing.html
- [ ] Review UEFI firmware update and capsule services: https://uefi.org/specs/UEFI/2.11/23_Firmware_Update_and_Reporting.html
- [ ] Review ACPI Specification 6.6 or the current superseding revision: https://uefi.org/specs/ACPI/6.6/
- [ ] Review the UEFI Platform Initialization specification index and current revision: https://uefi.org/specifications
- [ ] Review SMBIOS 3.9.0 or the current superseding revision: https://www.dmtf.org/standards/smbios

### 146.2 Processor and ABI

- [ ] Review AMD64 Architecture Programmer's Manual volumes and current revisions: https://docs.amd.com/
- [ ] Review AMD64 Architecture Programmer's Manual Volume 1: https://docs.amd.com/v/u/en-US/24592_3.24
- [ ] Review AMD64 Architecture Programmer's Manual Volume 2: https://docs.amd.com/v/u/en-US/24593_3.44_APM_Vol2
- [ ] Review AMD64 Architecture Programmer's Manual Volume 3: https://docs.amd.com/v/u/en-US/24594_3.37
- [ ] Review the consolidated AMD64 Architecture Programmer's Manual: https://docs.amd.com/v/u/en-US/40332_4.09_APM_PUB
- [ ] Review the AMD processor revision guide for the exact target family and stepping through https://docs.amd.com/
- [ ] Review AMD I/O virtualization documentation, including document 48882, through https://docs.amd.com/
- [ ] Review Intel 64 and IA-32 Software Developer Manuals for cross-vendor x86-64 details and future support: https://www.intel.com/content/www/us/en/developer/articles/technical/intel-sdm.html
- [ ] Review the x86-64 System V ABI source: https://gitlab.com/x86-psABIs/x86-64-ABI
- [ ] Review the ELF Generic ABI: https://www.sco.com/developers/gabi/latest/contents.html
- [ ] Review Microsoft PE/COFF documentation for UEFI images: https://learn.microsoft.com/en-us/windows/win32/debug/pe-format
- [ ] Review DWARF Version 5 and current working-status information: https://dwarfstd.org/
- [ ] Review ISO/IEC 9899:2024 for the C language: https://www.iso.org/standard/82075.html
- [ ] Review ISO/IEC 14882:2024 if C++ is used: https://www.iso.org/standard/83626.html

### 146.3 PCIe, storage, USB, and timers

- [ ] Review the PCI-SIG specifications index and the revision implemented by the target hardware: https://pcisig.com/specifications
- [ ] Review the NVM Express specifications index and current ratified base and command-set revisions: https://nvmexpress.org/specifications/
- [ ] Review the NVM Express Base Specification 2.2 reference copy where applicable: https://nvmexpress.org/wp-content/uploads/NVM-Express-Base-Specification-Revision-2.2-2025.03.11-Ratified.pdf
- [ ] Review Serial ATA AHCI 1.3.1: https://www.intel.com/content/dam/www/public/us/en/documents/technical-specifications/serial-ata-ahci-spec-rev1-3-1.pdf
- [ ] Review xHCI 1.2 or the exact controller-supported revision: https://www.intel.com/content/dam/www/public/us/en/documents/technical-specifications/extensible-host-controler-interface-usb-xhci.pdf
- [ ] Review USB 2.0: https://www.usb.org/document-library/usb-20-specification
- [ ] Review USB 3.2 Revision 1.1: https://www.usb.org/document-library/usb-32-revision-11-june-2022
- [ ] Review USB4 only if target hardware support is implemented: https://www.usb.org/usb4
- [ ] Review USB Type-C specifications only if Type-C policy or alt modes are implemented: https://www.usb.org/document-library/usb-type-cr-cable-and-connector-specification-release-25
- [ ] Review HID 1.11 and current HID Usage Tables: https://www.usb.org/hid
- [ ] Review USB Mass Storage Bulk-Only Transport: https://www.usb.org/document-library/mass-storage-bulk-only-10
- [ ] Review USB Attached SCSI bootability and transport references: https://www.usb.org/document-library/usb-mass-storage-class-specification-uasp-bootability-v10-and-adopters-agreement
- [ ] Review USB audio class specifications if audio devices are targeted: https://www.usb.org/document-library/usb-audio-devices-release-40-and-adopters-agreement
- [ ] Review USB CDC class definitions if CDC devices are targeted: https://www.usb.org/document-library/class-definitions-communication-devices-12
- [ ] Review High Precision Event Timer 1.0a: https://www.intel.com/content/dam/www/public/us/en/documents/technical-specifications/software-developers-hpet-spec-1-0a.pdf

### 146.4 Security and trusted platform

- [ ] Review TPM 2.0 Library Specification and errata: https://trustedcomputinggroup.org/resource/tpm-library-specification/
- [ ] Review the TCG PC Client Platform Firmware Profile: https://trustedcomputinggroup.org/resource/pc-client-specific-platform-firmware-profile-specification/
- [ ] Review the TCG PC Client TPM Profile: https://trustedcomputinggroup.org/wp-content/uploads/PC-Client-Specific-Platform-TPM-Profile-for-TPM-2p0-Version-1p06_pub.pdf
- [ ] Review NIST SP 800-90A for deterministic random bit generators: https://csrc.nist.gov/pubs/sp/800/90/a/r1/final
- [ ] Review NIST SP 800-90B and the random-bit-generation publication index: https://csrc.nist.gov/Projects/random-bit-generation/publications
- [ ] Review NIST FIPS publications and current cryptographic standards: https://csrc.nist.gov/publications/fips
- [ ] Review NIST SP 800-193 Platform Firmware Resiliency Guidelines: https://csrc.nist.gov/pubs/sp/800/193/final
- [ ] Review NIST SP 800-218 Secure Software Development Framework: https://csrc.nist.gov/pubs/sp/800/218/final

### 146.5 User ABI, text, time, and internationalization

- [ ] Review POSIX.1-2024 Issue 8 as an interface and utility reference: https://pubs.opengroup.org/onlinepubs/9799919799/
- [ ] Review Unicode 17.0 or the current superseding version: https://www.unicode.org/versions/latest/
- [ ] Review the Unicode core specification: https://www.unicode.org/versions/Unicode17.0.0/core-spec/
- [ ] Review the Unicode Character Database and annexes required for segmentation, normalization, bidi, security, and line breaking: https://www.unicode.org/versions/Unicode17.0.0/
- [ ] Review the IANA Time Zone Database: https://www.iana.org/time-zones
- [ ] Review CLDR only if localized formatting and locale data are implemented: https://cldr.unicode.org/

### 146.6 Ethernet, Wi-Fi, Bluetooth, and Internet protocols

- [ ] Review IEEE 802.3-2022 or the current superseding Ethernet standard: https://standards.ieee.org/ieee/802.3/10422/
- [ ] Review IEEE 802.11-2024 or the current superseding wireless LAN standard: https://standards.ieee.org/ieee/802.11/10548/
- [ ] Review the Bluetooth specification index: https://www.bluetooth.com/specifications/specs/
- [ ] Review Bluetooth Core Specification 6.2 or the exact controller-supported revision: https://www.bluetooth.com/specifications/specs/core-specification-6-2/
- [ ] Review the IETF RFC process and always check updates and errata: https://www.ietf.org/process/rfcs/
- [ ] Review ARP in RFC 826: https://datatracker.ietf.org/doc/rfc826/
- [ ] Review IPv4 in RFC 791 and all applicable updates: https://datatracker.ietf.org/doc/rfc791/
- [ ] Review ICMPv4 in RFC 792 and applicable updates: https://datatracker.ietf.org/doc/rfc792/
- [ ] Review UDP in RFC 768 and applicable updates: https://datatracker.ietf.org/doc/rfc768/
- [ ] Review TCP in RFC 9293 and applicable updates: https://datatracker.ietf.org/doc/rfc9293/
- [ ] Review IPv6 in RFC 8200: https://datatracker.ietf.org/doc/rfc8200/
- [ ] Review ICMPv6 in RFC 4443: https://datatracker.ietf.org/doc/rfc4443/
- [ ] Review IPv6 Neighbor Discovery in RFC 4861: https://datatracker.ietf.org/doc/rfc4861/
- [ ] Review IPv6 SLAAC in RFC 4862: https://datatracker.ietf.org/doc/rfc4862/
- [ ] Review IPv6 Path MTU Discovery in RFC 8201: https://datatracker.ietf.org/doc/rfc8201/
- [ ] Review DHCPv4 in RFC 2131: https://datatracker.ietf.org/doc/rfc2131/
- [ ] Review DHCPv6 in RFC 8415: https://datatracker.ietf.org/doc/rfc8415/
- [ ] Review DNS concepts and implementation in RFC 1034 and RFC 1035: https://datatracker.ietf.org/doc/rfc1034/ and https://datatracker.ietf.org/doc/rfc1035/
- [ ] Review NTPv4 in RFC 5905: https://datatracker.ietf.org/doc/rfc5905/
- [ ] Review Network Time Security in RFC 8915 if implemented: https://datatracker.ietf.org/doc/rfc8915/
- [ ] Review TLS 1.3 in RFC 8446: https://datatracker.ietf.org/doc/rfc8446/
- [ ] Review HTTP semantics in RFC 9110 if an HTTP stack is implemented: https://datatracker.ietf.org/doc/rfc9110/
- [ ] Review HTTP/1.1 in RFC 9112 if implemented: https://datatracker.ietf.org/doc/rfc9112/
- [ ] Review HTTP/2 in RFC 9113 if implemented: https://datatracker.ietf.org/doc/rfc9113/
- [ ] Review QUIC in RFC 9000 and HTTP/3 in RFC 9114 only if implemented: https://datatracker.ietf.org/doc/rfc9000/ and https://datatracker.ietf.org/doc/rfc9114/
- [ ] Review mDNS in RFC 6762 only if implemented: https://datatracker.ietf.org/doc/rfc6762/

### 146.7 Graphics and display

- [ ] Review VESA standards availability, licensing, and access requirements: https://vesa.org/standards-specifications/
- [ ] Review VESA DisplayID information and obtain the exact normative revision required: https://vesa.org/featured-articles/vesa-rolls-out-displayid-version-2-0-standard-to-optimize-plug-and-play-connectivity-for-leading-edge-displays/
- [ ] Obtain the normative EDID, DisplayID, DisplayPort, HDMI, CTA-861, and HDCP documents lawfully before implementing their covered features.
- [ ] Review Vulkan 1.4 and current specifications if Vulkan compatibility is targeted: https://vulkan.org/
- [ ] Review the Vulkan registry and conformance materials: https://registry.khronos.org/vulkan/
- [ ] Review OpenGL 4.6 and GLSL 4.60 if OpenGL compatibility is targeted: https://registry.khronos.org/OpenGL/index_gl.php
- [ ] Review SPIR-V specifications if a shader toolchain is implemented: https://registry.khronos.org/SPIR-V/
- [ ] Review Wayland protocol concepts as a design reference if a similar compositor protocol is desired: https://wayland.freedesktop.org/docs/html
- [ ] Review the official NVIDIA open GPU kernel modules only as a Linux-specific source reference, not a drop-in PooleOS driver: https://github.com/NVIDIA/open-gpu-kernel-modules
- [ ] Review NVIDIA public developer documentation and licensing before using firmware or interfaces: https://developer.nvidia.com/

### 146.8 Build, provenance, and software supply chain

- [ ] Review the definition and practices for reproducible builds: https://reproducible-builds.org/docs/definition/
- [ ] Review SPDX specifications and current version: https://spdx.dev/use/specifications/
- [ ] Review SLSA 1.2 or the current superseding specification: https://slsa.dev/spec/v1.2/
- [ ] Review source-control signing, protected branches, and artifact retention policies for the chosen forge.
- [ ] Review every compiler, linker, assembler, and runtime license used in the toolchain.

## 147. PooleOS Release Manifest Fields

- [ ] Record PooleOS release version.
- [ ] Record release channel.
- [ ] Record release date.
- [ ] Record source commit.
- [ ] Record source tree hash.
- [ ] Record toolchain manifest hash.
- [ ] Record build environment hash.
- [ ] Record bootloader version and hash.
- [ ] Record kernel version and hash.
- [ ] Record initramfs hash.
- [ ] Record system image hash.
- [ ] Record recovery image hash.
- [ ] Record package repository snapshot.
- [ ] Record package list.
- [ ] Record firmware list and hashes.
- [ ] Record microcode list and hashes.
- [ ] Record driver list and hashes.
- [ ] Record filesystem format version.
- [ ] Record package format version.
- [ ] Record user ABI version.
- [ ] Record syscall ABI version.
- [ ] Record driver ABI version.
- [ ] Record PooleGlyph version.
- [ ] Record PDC component versions.
- [ ] Record PDC receipt schema version.
- [ ] Record supported hardware identifiers.
- [ ] Record required firmware versions.
- [ ] Record known incompatible hardware.
- [ ] Record known issues.
- [ ] Record security fixes.
- [ ] Record migration requirements.
- [ ] Record rollback limitations.
- [ ] Record SBOM hash.
- [ ] Record provenance hash.
- [ ] Record artifact signatures.
- [ ] Record signing key fingerprints.
- [ ] Record test suite receipt hashes.
- [ ] Record benchmark receipt hashes.
- [ ] Record release approval.

## 148. Serial, UART, and Emergency Console Infrastructure

### 148.1 Serial controller discovery

- [ ] Parse ACPI SPCR before assuming a legacy serial port address.
- [ ] Parse ACPI DBG2 when present.
- [ ] Parse PCI serial-controller class devices.
- [ ] Parse platform-specific serial device descriptions from ACPI namespace.
- [ ] Support an explicitly configured legacy COM1 fallback only when the platform target permits it.
- [ ] Support an explicitly configured legacy COM2 fallback only when the platform target permits it.
- [ ] Do not probe arbitrary I/O ports destructively.
- [ ] Record controller type, base address, register spacing, access width, clock, baud, parity, and flow-control defaults.
- [ ] Reserve serial I/O resources through the device-resource manager.
- [ ] Prevent two drivers from binding to the same serial controller.
- [ ] Expose serial-controller identity in the hardware manifest.

### 148.2 8250/16450/16550-compatible UART driver

- [ ] Implement receive-buffer register access.
- [ ] Implement transmit-holding register access.
- [ ] Implement interrupt-enable register access.
- [ ] Implement interrupt-identification register access.
- [ ] Implement FIFO-control register access.
- [ ] Implement line-control register access.
- [ ] Implement modem-control register access.
- [ ] Implement line-status register access.
- [ ] Implement modem-status register access.
- [ ] Implement scratch-register access where implemented.
- [ ] Implement divisor-latch access with DLAB sequencing.
- [ ] Calculate baud-rate divisors without overflow.
- [ ] Validate requested baud rates against controller clock and divisor limits.
- [ ] Implement 5-bit character mode only if required.
- [ ] Implement 6-bit character mode only if required.
- [ ] Implement 7-bit character mode.
- [ ] Implement 8-bit character mode.
- [ ] Implement one-stop-bit mode.
- [ ] Implement supported multi-stop-bit modes.
- [ ] Implement no-parity mode.
- [ ] Implement odd-parity mode.
- [ ] Implement even-parity mode.
- [ ] Implement mark and space parity only if hardware and API require them.
- [ ] Detect FIFO presence.
- [ ] Configure receive FIFO trigger level.
- [ ] Clear receive FIFO safely.
- [ ] Clear transmit FIFO safely.
- [ ] Enable and disable FIFOs safely.
- [ ] Implement polling transmit before interrupt infrastructure exists.
- [ ] Implement polling receive for recovery mode.
- [ ] Implement interrupt-driven transmit.
- [ ] Implement interrupt-driven receive.
- [ ] Drain all pending interrupt causes without livelock.
- [ ] Implement receive ring buffer.
- [ ] Implement transmit ring buffer.
- [ ] Define ring-buffer overflow behavior.
- [ ] Record overrun errors.
- [ ] Record parity errors.
- [ ] Record framing errors.
- [ ] Record break conditions.
- [ ] Record transmitter-empty state.
- [ ] Implement RTS and CTS hardware flow control when supported.
- [ ] Implement DTR and DSR handling when required.
- [ ] Implement carrier-detect handling when required.
- [ ] Implement software XON/XOFF only as an optional terminal policy.
- [ ] Handle unplugged or nonresponsive serial adapters.
- [ ] Handle spurious UART interrupts.
- [ ] Rate-limit serial error logs.

### 148.3 Serial console and diagnostics

- [ ] Create an early serial-console sink that requires no heap allocation.
- [ ] Create a panic-safe serial-console sink that requires no locks.
- [ ] Create an NMI-safe best-effort serial-output path where feasible.
- [ ] Serialize normal multi-CPU console output.
- [ ] Avoid deadlock when panic interrupts a console writer.
- [ ] Provide an emergency direct-output path that may sacrifice formatting.
- [ ] Support serial input for the recovery shell only under explicit policy.
- [ ] Disable serial login by default on production desktop builds.
- [ ] Require authentication before privileged serial recovery access.
- [ ] Redact secrets, keys, and protected pointers from serial logs.
- [ ] Support configurable newline translation.
- [ ] Support configurable baud and framing on the kernel command line.
- [ ] Expose serial-console status to user space.
- [ ] Provide a user-space terminal device for non-console UARTs.
- [ ] Test boot with no UART present.
- [ ] Test boot with a stuck transmit-ready bit.
- [ ] Test boot with continuous receive traffic.
- [ ] Test high-rate transmit and receive.
- [ ] Test parity, framing, and overrun fault paths.
- [ ] Test panic output before and after interrupt initialization.
- [ ] Test panic output during allocator failure.
- [ ] Test serial-console handoff from bootloader to kernel.

## 149. RTC, CMOS, Firmware Variables, and Wake Alarms

### 149.1 CMOS and RTC access

- [ ] Identify whether a PC-compatible RTC is present through platform policy and ACPI data.
- [ ] Serialize access to CMOS index and data ports.
- [ ] Preserve the NMI-mask bit when selecting CMOS registers.
- [ ] Define whether NMI masking is ever permitted during RTC access.
- [ ] Avoid writing undocumented CMOS offsets.
- [ ] Read RTC register A update-in-progress state.
- [ ] Read RTC register B data-mode and hour-mode bits.
- [ ] Read RTC register D valid-RAM-and-time status.
- [ ] Read seconds, minutes, hours, weekday, day, month, and year fields.
- [ ] Read the ACPI century register when defined.
- [ ] Handle platforms without a century register.
- [ ] Convert BCD values when RTC is in BCD mode.
- [ ] Handle binary values when RTC is in binary mode.
- [ ] Convert 12-hour values and PM indication.
- [ ] Handle 24-hour values.
- [ ] Read a stable RTC snapshot without crossing an update boundary.
- [ ] Set a bounded timeout while waiting for update-in-progress to clear.
- [ ] Reject impossible calendar fields.
- [ ] Reject invalid leap-day values.
- [ ] Define a policy for years when century information is absent.
- [ ] Treat the hardware clock as UTC.
- [ ] Do not apply local timezone offsets in the kernel.
- [ ] Detect RTC battery or validity failure.
- [ ] Expose RTC validity and source information.
- [ ] Record RTC read failures without blocking boot indefinitely.

### 149.2 RTC interrupts and alarms

- [ ] Decide whether periodic RTC interrupts are supported.
- [ ] Decide whether update-ended RTC interrupts are supported.
- [ ] Decide whether alarm interrupts are supported.
- [ ] Configure RTC interrupt-enable bits without clobbering unrelated bits.
- [ ] Read register C to acknowledge RTC interrupts where required.
- [ ] Route the RTC interrupt through the platform interrupt framework.
- [ ] Implement wake-alarm programming only after ACPI wake support exists.
- [ ] Validate wake-alarm ranges.
- [ ] Handle alarms crossing month and year boundaries.
- [ ] Clear stale alarm state before arming a new alarm.
- [ ] Prevent unprivileged applications from programming system wake alarms directly.
- [ ] Arbitrate multiple user-space wake requests.
- [ ] Persist the earliest authorized wake request.
- [ ] Report wake source after resume.
- [ ] Test wake alarm from soft-off only on sacrificial hardware.
- [ ] Test wake alarm from supported sleep states.
- [ ] Test canceled alarms.
- [ ] Test RTC interrupt storms.

### 149.3 UEFI variables and nonvolatile settings

- [ ] Map UEFI runtime-service regions with required attributes.
- [ ] Preserve firmware runtime mappings across the kernel page-table transition.
- [ ] Implement GetVariable wrapper.
- [ ] Implement GetNextVariableName wrapper.
- [ ] Implement SetVariable wrapper only after privilege and integrity policy exist.
- [ ] Implement QueryVariableInfo wrapper.
- [ ] Validate variable-name UTF-16 encoding.
- [ ] Validate vendor GUIDs.
- [ ] Validate attribute combinations.
- [ ] Enforce maximum variable sizes.
- [ ] Enforce platform-reported storage limits.
- [ ] Handle out-of-resource responses.
- [ ] Handle authenticated variable requirements.
- [ ] Prevent unprivileged Secure Boot variable modification.
- [ ] Prevent unprivileged boot-entry modification.
- [ ] Prevent variable-store exhaustion attacks.
- [ ] Rate-limit nonessential variable writes.
- [ ] Avoid using firmware variables as a high-frequency database.
- [ ] Record firmware-variable write failures.
- [ ] Implement recovery for malformed PooleOS-owned variables.
- [ ] Namespace all PooleOS-owned variables under a dedicated GUID.
- [ ] Version every PooleOS-owned variable payload.
- [ ] Checksum or authenticate PooleOS-owned variable payloads.
- [ ] Provide a tool to list and export variables safely.
- [ ] Provide a tool to delete only PooleOS-owned variables.
- [ ] Test variable operations under Secure Boot enabled and disabled states.
- [ ] Test full variable-store behavior in virtual firmware before real hardware.

## 150. Loadable Kernel Modules, Driver Packages, and Runtime Extension Control

### 150.1 Module format and loader

- [ ] Decide whether production kernels permit loadable modules.
- [ ] Define the module container format.
- [ ] Define the supported ELF object type and machine architecture.
- [ ] Define supported section types.
- [ ] Define supported relocation types.
- [ ] Reject unsupported relocation types.
- [ ] Validate ELF headers before allocation.
- [ ] Validate section-table bounds.
- [ ] Validate symbol-table bounds.
- [ ] Validate string-table bounds.
- [ ] Validate relocation target bounds.
- [ ] Prevent integer overflow in all module-size calculations.
- [ ] Allocate separate module text, read-only data, writable data, and executable trampolines where unavoidable.
- [ ] Apply relocations while mappings are writable and non-executable.
- [ ] Enforce W^X after relocation.
- [ ] Mark read-only-after-initialization data immutable.
- [ ] Resolve imported kernel symbols through an explicit export table.
- [ ] Hide non-exported kernel symbols.
- [ ] Version exported symbols or version the complete module ABI.
- [ ] Reject modules built for incompatible kernel ABI versions.
- [ ] Support module initialization entry point.
- [ ] Support module cleanup entry point.
- [ ] Run constructors only if the module ABI defines them.
- [ ] Run destructors only if the module ABI defines them.
- [ ] Register unwind and debug information.
- [ ] Unregister unwind and debug information on unload.
- [ ] Flush instruction caches where required by architecture.
- [ ] Synchronize all CPUs before executing newly loaded code when required.

### 150.2 Module identity, trust, and dependency management

- [ ] Assign a unique module name.
- [ ] Assign a semantic module version.
- [ ] Record source commit and build identifier.
- [ ] Record license metadata.
- [ ] Record signer identity.
- [ ] Record required kernel ABI version.
- [ ] Record required module dependencies.
- [ ] Record optional dependencies.
- [ ] Record conflicting modules.
- [ ] Record supported device identifiers.
- [ ] Record firmware dependencies.
- [ ] Record required configuration options.
- [ ] Sign module packages.
- [ ] Verify module signatures before parsing executable sections where practical.
- [ ] Anchor trust in an offline-controlled key hierarchy.
- [ ] Support key revocation.
- [ ] Support module revocation lists.
- [ ] Prevent downgrade to a revoked module version.
- [ ] Verify package hashes before load.
- [ ] Resolve dependencies without cycles.
- [ ] Detect dependency cycles.
- [ ] Load dependencies in deterministic order.
- [ ] Unload dependents before dependencies.
- [ ] Expose loaded-module metadata to privileged diagnostics.
- [ ] Mark unsigned or development modules as tainting the kernel.
- [ ] Record module load and unload events in the audit log.

### 150.3 Safe load, unload, and failure handling

- [ ] Require a module reference for every active object, open handle, interrupt, callback, timer, work item, mapping, and device binding.
- [ ] Prevent unload while references remain.
- [ ] Stop new references before unload begins.
- [ ] Quiesce device I/O before unload.
- [ ] Disable and synchronize interrupts before freeing interrupt handlers.
- [ ] Cancel and drain timers.
- [ ] Cancel and drain work queues.
- [ ] Wait for read-copy-update grace periods where used.
- [ ] Unregister user-visible interfaces.
- [ ] Unbind devices safely.
- [ ] Release DMA mappings.
- [ ] Release MMIO and I/O-port resources.
- [ ] Release firmware references.
- [ ] Release allocated memory.
- [ ] Zero sensitive module memory before release.
- [ ] Handle initialization failure at every partial stage.
- [ ] Roll back initialization in reverse order.
- [ ] Prevent recursive module loading deadlocks.
- [ ] Prevent concurrent duplicate loads.
- [ ] Prevent unload from module-owned execution context.
- [ ] Provide forced unload only in nonproduction diagnostic builds.
- [ ] Treat forced unload as an unsupported tainted state.
- [ ] Test repeated load/unload cycles.
- [ ] Test load failure after each initialization stage.
- [ ] Fuzz module metadata and relocation parsing.
- [ ] Test module revocation.
- [ ] Test recovery when a module crashes during probe.

### 150.4 User-space module and driver management

- [ ] Provide a privileged module loader service.
- [ ] Provide a read-only module listing tool.
- [ ] Provide dependency inspection.
- [ ] Provide signer and hash inspection.
- [ ] Provide device-to-driver alias resolution.
- [ ] Load boot-critical modules from the signed initramfs.
- [ ] Load noncritical modules after the root filesystem is trusted.
- [ ] Apply denylist policy before automatic loading.
- [ ] Apply allowlist policy for recovery builds.
- [ ] Require explicit authorization for experimental drivers.
- [ ] Persist module configuration outside the immutable system image only through validated policy files.
- [ ] Validate module parameters by type and range.
- [ ] Redact secret parameters.
- [ ] Record the exact active module set in benchmark receipts.
- [ ] Disable automatic module loading in hardened modes if policy requires it.

## 151. Memory Reclaim, Page Replacement, Compaction, and Out-of-Memory Control

### 151.1 Page classification and reclaimability

- [ ] Classify free pages.
- [ ] Classify anonymous pages.
- [ ] Classify file-backed clean pages.
- [ ] Classify file-backed dirty pages.
- [ ] Classify writeback pages.
- [ ] Classify swap-backed pages.
- [ ] Classify unevictable pages.
- [ ] Classify pinned DMA pages.
- [ ] Classify mlocked pages.
- [ ] Classify kernel slab pages.
- [ ] Classify page-table pages.
- [ ] Classify executable file mappings.
- [ ] Classify shared-memory pages.
- [ ] Classify huge pages.
- [ ] Classify device-mapped pages.
- [ ] Track page reference state.
- [ ] Track page dirty state.
- [ ] Track page writeback state.
- [ ] Track page mapping and reverse mapping.
- [ ] Track page ownership and accounting domain.
- [ ] Prevent reclaim of pages with active hardware ownership.
- [ ] Prevent reclaim of firmware runtime pages.
- [ ] Prevent reclaim of crash-kernel reservations.

### 151.2 Watermarks and background reclaim

- [ ] Define minimum free-memory watermarks per zone.
- [ ] Define low watermarks per zone.
- [ ] Define high watermarks per zone.
- [ ] Scale watermarks for system memory size.
- [ ] Reserve emergency memory for critical kernel paths.
- [ ] Start a background reclaim thread per required memory domain.
- [ ] Wake background reclaim below the low watermark.
- [ ] Stop background reclaim above the high watermark.
- [ ] Balance reclaim across zones.
- [ ] Balance reclaim across NUMA nodes when supported.
- [ ] Avoid reclaiming from unreachable or offline memory.
- [ ] Limit reclaim CPU consumption.
- [ ] Measure pages scanned.
- [ ] Measure pages reclaimed.
- [ ] Measure reclaim efficiency.
- [ ] Detect reclaim thrashing.
- [ ] Detect writeback congestion.
- [ ] Back off when storage cannot accept writeback.
- [ ] Prioritize clean file-cache eviction when appropriate.
- [ ] Preserve working sets under light pressure.
- [ ] Expose reclaim telemetry.

### 151.3 Direct reclaim and allocation failure

- [ ] Define which allocation contexts may enter direct reclaim.
- [ ] Prevent interrupt context from sleeping in reclaim.
- [ ] Prevent recursive filesystem reclaim deadlocks.
- [ ] Tag allocations that must not invoke filesystem writeback.
- [ ] Tag allocations that must not invoke I/O.
- [ ] Bound direct-reclaim effort.
- [ ] Retry reclaim only under explicit allocation policies.
- [ ] Support no-fail allocations only for truly unrecoverable paths with reserved memory.
- [ ] Return allocation failure to recoverable callers.
- [ ] Propagate memory-pressure errors through subsystem APIs.
- [ ] Avoid holding global locks across direct reclaim.
- [ ] Avoid reclaiming memory needed to complete reclaim I/O.
- [ ] Test direct reclaim under nested filesystem operations.
- [ ] Test allocator failure in every privileged daemon.

### 151.4 Replacement policy and working-set control

- [ ] Choose a page-replacement policy.
- [ ] Separate anonymous and file-backed pressure accounting.
- [ ] Maintain active and inactive generations or an equivalent aging model.
- [ ] Promote recently referenced pages.
- [ ] Demote cold pages.
- [ ] Use hardware accessed bits safely.
- [ ] Clear accessed bits without losing concurrent references.
- [ ] Handle shared pages referenced by multiple processes.
- [ ] Handle executable mappings.
- [ ] Handle memory-mapped database workloads.
- [ ] Handle sequential file scans without evicting the complete working set.
- [ ] Implement readahead interaction with replacement policy.
- [ ] Implement drop-behind hints where appropriate.
- [ ] Support application memory-advice interfaces.
- [ ] Support filesystem cache hints.
- [ ] Prevent untrusted applications from forcing global cache eviction.
- [ ] Record major and minor fault rates.
- [ ] Record refault distance or an equivalent thrashing signal.

### 151.5 Slab and kernel-object reclaim

- [ ] Register shrink callbacks for reclaimable kernel caches.
- [ ] Define shrinker ordering and recursion rules.
- [ ] Count reclaimable objects accurately.
- [ ] Avoid blocking under allocator-internal locks.
- [ ] Reclaim dentries and inode caches safely.
- [ ] Reclaim network caches safely.
- [ ] Reclaim filesystem metadata safely.
- [ ] Reclaim graphics objects only after fences and references permit it.
- [ ] Reclaim deferred module data only after grace periods.
- [ ] Test shrinkers under concurrent object creation and deletion.
- [ ] Detect shrinker livelock.
- [ ] Expose per-cache reclaim statistics.

### 151.6 Compaction, fragmentation, and huge pages

- [ ] Measure external fragmentation by order.
- [ ] Implement movable-page classification.
- [ ] Migrate movable pages safely.
- [ ] Update all mappings during migration.
- [ ] Preserve dirty and referenced state during migration.
- [ ] Coordinate migration with DMA pinning.
- [ ] Coordinate migration with page faults.
- [ ] Compact memory for high-order allocations.
- [ ] Bound synchronous compaction latency.
- [ ] Run background compaction only under policy.
- [ ] Split huge pages safely.
- [ ] Collapse huge pages safely if supported.
- [ ] Avoid huge-page collapse during severe pressure.
- [ ] Expose compaction success and failure metrics.
- [ ] Test long-uptime fragmentation.

### 151.7 Swap and compressed-memory policy

- [ ] Define when anonymous memory may be swapped.
- [ ] Define swap priority across devices.
- [ ] Reserve swap metadata memory.
- [ ] Authenticate or encrypt swap according to system policy.
- [ ] Track swap slots.
- [ ] Prevent duplicate slot allocation.
- [ ] Handle swap-device removal.
- [ ] Handle swap I/O error.
- [ ] Readahead adjacent swap entries only when beneficial.
- [ ] Avoid swap storms.
- [ ] Implement compressed RAM swap only as an optional independent subsystem.
- [ ] Bound compressed-memory CPU and RAM overhead.
- [ ] Handle incompressible pages.
- [ ] Verify decompressed page integrity where feasible.
- [ ] Test swap under power loss and device failure.

### 151.8 Out-of-memory policy

- [ ] Detect unrecoverable allocation pressure.
- [ ] Distinguish global OOM from per-resource-group OOM.
- [ ] Choose OOM victims through documented criteria.
- [ ] Protect PID 1 and recovery-critical services by policy, not absolute immunity to deadlock.
- [ ] Protect the storage and logging paths needed to recover.
- [ ] Account shared memory without double-counting.
- [ ] Account pinned and unevictable memory.
- [ ] Consider recent allocation growth.
- [ ] Consider process importance and user policy.
- [ ] Allow services to set bounded OOM preferences.
- [ ] Prevent unprivileged processes from making themselves permanently unkillable.
- [ ] Notify the selected victim.
- [ ] Terminate all required threads in the victim domain.
- [ ] Reap memory without waiting indefinitely for user-space cleanup.
- [ ] Escalate when a victim cannot exit.
- [ ] Record an OOM report with memory statistics and allocation context.
- [ ] Rate-limit repeated OOM reports.
- [ ] Trigger safe mode or reboot only under explicit policy.
- [ ] Test global OOM.
- [ ] Test per-user OOM.
- [ ] Test per-service OOM.
- [ ] Test OOM while storage is stalled.
- [ ] Test OOM while graphics memory is pinned.

### 151.9 Memory pressure interfaces and tests

- [ ] Expose current free and available memory.
- [ ] Expose reclaimable file cache.
- [ ] Expose dirty and writeback memory.
- [ ] Expose anonymous memory.
- [ ] Expose swap usage.
- [ ] Expose pinned and unevictable memory.
- [ ] Expose per-domain pressure-stall time.
- [ ] Provide event thresholds for memory pressure.
- [ ] Allow services to shed caches voluntarily.
- [ ] Allow applications to receive low-memory notifications.
- [ ] Prevent notification storms.
- [ ] Create deterministic low-memory test harnesses.
- [ ] Inject page-allocation failures by call site.
- [ ] Inject reclaim failures.
- [ ] Inject swap I/O failures.
- [ ] Run long-duration leak tests.
- [ ] Run mixed memory and storage stress tests.
- [ ] Verify no data corruption after page migration and reclaim.

## 152. I2C, SMBus, SPI, GPIO, Embedded Controller, and Super I/O

### 152.1 Common low-speed bus framework

- [ ] Define controller objects.
- [ ] Define bus-segment objects.
- [ ] Define device-address objects.
- [ ] Define transaction objects.
- [ ] Define synchronous transfer API.
- [ ] Define asynchronous transfer API only if required.
- [ ] Define timeout semantics.
- [ ] Define cancellation semantics.
- [ ] Define bus locking.
- [ ] Define per-device locking.
- [ ] Define controller reset and recovery.
- [ ] Define transfer tracing with secret-data redaction.
- [ ] Define firmware-described devices.
- [ ] Define manually declared development devices only under explicit configuration.
- [ ] Prevent unrestricted user-space access to motherboard management buses.
- [ ] Expose read-only diagnostic access only through policy.

### 152.2 I2C controller and protocol support

- [ ] Obtain the exact controller programming documentation.
- [ ] Implement controller reset.
- [ ] Implement controller enable and disable.
- [ ] Configure bus speed within controller and device limits.
- [ ] Implement START condition.
- [ ] Implement repeated START.
- [ ] Implement STOP condition.
- [ ] Implement 7-bit addressing.
- [ ] Implement 10-bit addressing only if required.
- [ ] Implement read transfers.
- [ ] Implement write transfers.
- [ ] Implement combined write-then-read transfers.
- [ ] Handle ACK.
- [ ] Handle NACK on address.
- [ ] Handle NACK on data.
- [ ] Handle arbitration loss if multi-controller mode is possible.
- [ ] Handle clock stretching.
- [ ] Apply bounded transfer timeouts.
- [ ] Detect stuck-low SDA.
- [ ] Detect stuck-low SCL.
- [ ] Implement safe bus-recovery clock pulses only where electrical design permits it.
- [ ] Reset the controller after a wedged transfer.
- [ ] Handle zero-length transfers according to API policy.
- [ ] Handle controllers with FIFO and DMA support.
- [ ] Handle controllers requiring polling.
- [ ] Handle controllers requiring interrupts.
- [ ] Prevent concurrent transactions from interleaving.
- [ ] Preserve transaction atomicity across repeated START.
- [ ] Test every supported bus frequency.
- [ ] Test NACK, arbitration loss, timeout, and stuck-bus paths.

### 152.3 SMBus protocol support

- [ ] Implement quick command only if required.
- [ ] Implement send byte.
- [ ] Implement receive byte.
- [ ] Implement write byte.
- [ ] Implement read byte.
- [ ] Implement write word.
- [ ] Implement read word.
- [ ] Implement process call.
- [ ] Implement block write.
- [ ] Implement block read.
- [ ] Implement block write-block read process call if required.
- [ ] Implement packet error checking.
- [ ] Validate PEC on receive.
- [ ] Generate PEC on transmit.
- [ ] Implement SMBALERT handling where wired.
- [ ] Implement alert-response protocol where required.
- [ ] Implement host-notify protocol where supported.
- [ ] Implement controller and target timeouts required by the selected SMBus revision.
- [ ] Implement ACPI SMBus operation region if required.
- [ ] Prevent ordinary applications from changing voltage, clock, fan, or SPD devices.
- [ ] Test interoperability with I2C devices only within documented electrical and protocol limits.

### 152.4 SPI support

- [ ] Treat SPI as controller- and device-specific rather than assuming a single universal discovery standard.
- [ ] Define SPI controller API.
- [ ] Define chip-select identity.
- [ ] Define clock polarity.
- [ ] Define clock phase.
- [ ] Define bits per word.
- [ ] Define bit order.
- [ ] Define maximum clock frequency per device.
- [ ] Define full-duplex transfers.
- [ ] Define half-duplex transfers.
- [ ] Define transmit-only transfers.
- [ ] Define receive-only transfers.
- [ ] Support scatter/gather transfers only when controller permits it.
- [ ] Hold or release chip select between transfer segments as requested.
- [ ] Implement polling transfers.
- [ ] Implement interrupt-driven transfers.
- [ ] Implement DMA transfers only after DMA safety is established.
- [ ] Bound transfer duration.
- [ ] Handle controller underrun.
- [ ] Handle controller overrun.
- [ ] Handle device-ready GPIO if described.
- [ ] Prevent user-space writes to firmware flash or power controllers without a dedicated signed updater.
- [ ] Test all supported SPI modes.

### 152.5 GPIO support

- [ ] Define GPIO controller objects.
- [ ] Define line numbering independent of global unstable indices.
- [ ] Describe lines through firmware nodes.
- [ ] Request exclusive or shared line ownership according to controller capability.
- [ ] Configure input mode.
- [ ] Configure output mode.
- [ ] Configure initial output atomically where hardware permits.
- [ ] Read input value.
- [ ] Set output value.
- [ ] Configure active-high or active-low semantics.
- [ ] Configure pull-up and pull-down only when documented.
- [ ] Configure open-drain or open-source only when supported.
- [ ] Configure debounce only when supported.
- [ ] Configure edge interrupts.
- [ ] Configure level interrupts.
- [ ] Handle both-edge limitations.
- [ ] Prevent direction changes while a critical device uses the line.
- [ ] Preserve safe output state across suspend and resume.
- [ ] Prevent unprivileged raw motherboard GPIO access.
- [ ] Expose named, authorized GPIO functions through higher-level drivers.

### 152.6 ACPI embedded controller

- [ ] Discover the embedded controller through ACPI.
- [ ] Reserve EC command and data ports.
- [ ] Implement EC status polling with bounded timeouts.
- [ ] Implement EC command write.
- [ ] Implement EC data read and write.
- [ ] Implement burst mode only if required and tested.
- [ ] Serialize all EC transactions.
- [ ] Integrate ACPI EC operation regions.
- [ ] Handle EC query events.
- [ ] Dispatch `_Qxx` methods through the ACPI event path.
- [ ] Prevent AML and native drivers from racing for the EC.
- [ ] Avoid EC access in contexts that cannot sleep unless hardware and implementation permit it.
- [ ] Recover from EC timeout without an infinite firmware loop.
- [ ] Rate-limit failing EC queries.
- [ ] Treat undocumented EC commands as unsafe.
- [ ] Test power-button, thermal, battery, and fan-related EC paths only within the target platform's documentation.

### 152.7 LPC, eSPI, Super I/O, SPD, and optional I3C

- [ ] Determine whether LPC or eSPI devices must be supported on the target motherboard.
- [ ] Obtain chipset documentation before programming LPC or eSPI bridges.
- [ ] Enumerate firmware-described legacy devices.
- [ ] Implement Super I/O configuration entry only for explicitly supported chips.
- [ ] Identify Super I/O vendor and chip ID before register access.
- [ ] Exit Super I/O configuration mode reliably.
- [ ] Do not scan arbitrary Super I/O register banks on production hardware.
- [ ] Support hardware-monitor logical devices through chip-specific drivers only.
- [ ] Support serial-port logical devices through chip-specific drivers only.
- [ ] Support watchdog logical devices through chip-specific drivers only.
- [ ] Treat memory SPD as read-only by default.
- [ ] Discover DDR4 SPD access path where applicable.
- [ ] Discover DDR5 SPD hub and I3C Basic path only if documented.
- [ ] Never write DIMM SPD outside a dedicated recovery-capable engineering tool.
- [ ] Validate SPD checksums and CRCs.
- [ ] Expose SPD data with privacy and integrity policy.
- [ ] Record DIMM identity in hardware manifest only with user-approved serial-number handling.

## 153. Firmware, Microcode, and Device Update Infrastructure

### 153.1 Firmware inventory and policy

- [ ] Inventory motherboard firmware version.
- [ ] Inventory UEFI implementation and revision.
- [ ] Inventory embedded-controller firmware where exposed.
- [ ] Inventory CPU microcode revision on every CPU.
- [ ] Inventory GPU firmware and signed firmware blobs.
- [ ] Inventory NVMe firmware revisions.
- [ ] Inventory network-adapter firmware revisions.
- [ ] Inventory Bluetooth and Wi-Fi firmware blobs.
- [ ] Inventory peripheral firmware only when query is safe.
- [ ] Record firmware update capability and transport per component.
- [ ] Record whether rollback is supported.
- [ ] Record whether update requires AC power.
- [ ] Record whether update is destructive or may reset the device.
- [ ] Record vendor advisories and revoked versions.
- [ ] Separate operating-system packages from device firmware packages.
- [ ] Define which firmware can be redistributed.
- [ ] Define which firmware must be obtained from the vendor by the user.

### 153.2 UEFI capsule and ESRT update path

- [ ] Parse the EFI System Resource Table when present.
- [ ] Validate ESRT entry sizes and counts.
- [ ] Identify firmware resource GUIDs.
- [ ] Read current firmware versions.
- [ ] Read lowest supported firmware versions.
- [ ] Read capsule flags and update status.
- [ ] Stage capsule payloads in a protected location.
- [ ] Validate capsule headers and bounds.
- [ ] Validate capsule signatures through vendor-defined policy.
- [ ] Reject capsules for another platform or resource GUID.
- [ ] Reject versions below the lowest supported version.
- [ ] Enforce anti-rollback policy.
- [ ] Ensure adequate battery or AC power where applicable.
- [ ] Ensure adequate EFI System Partition space where required.
- [ ] Ensure recovery image availability before update.
- [ ] Schedule update on reboot.
- [ ] Communicate expected reboot behavior clearly.
- [ ] Preserve capsule across the required reboot path.
- [ ] Read and interpret firmware update result after reboot.
- [ ] Record update result and exact version.
- [ ] Prevent repeated reboot loops after failed capsule application.
- [ ] Support user cancellation before the irreversible stage.
- [ ] Never interrupt firmware update intentionally after vendor-defined commit point.
- [ ] Test capsule flow in virtual firmware where supported.

### 153.3 CPU microcode update

- [ ] Obtain signed microcode only from the processor vendor or trusted distribution channel.
- [ ] Validate microcode container structure.
- [ ] Match processor family, model, stepping, and platform identifiers.
- [ ] Reject incompatible patches.
- [ ] Record patch revision before update.
- [ ] Apply early microcode before enabling affected CPU features where required.
- [ ] Apply microcode to the bootstrap processor.
- [ ] Apply microcode to every application processor before scheduling user work.
- [ ] Verify patch revision after update.
- [ ] Handle CPUs that reject the patch.
- [ ] Keep all CPUs on a compatible revision.
- [ ] Reapply microcode after CPU hotplug or resume if architecture requires it.
- [ ] Include microcode hash and revision in benchmark receipts.
- [ ] Support microcode revocation through signed package policy.
- [ ] Preserve a safe boot path without a newly introduced bad microcode package when platform behavior permits.
- [ ] Test mixed success as a fatal or quarantined state according to architecture policy.

### 153.4 Device firmware updater framework

- [ ] Create one updater plugin per documented device family.
- [ ] Require exact PCI, USB, or platform identifiers.
- [ ] Require current-version query before update.
- [ ] Validate image format and checksum.
- [ ] Validate image signature when vendor supports it.
- [ ] Validate target compatibility.
- [ ] Validate downgrade and rollback rules.
- [ ] Quiesce all device users.
- [ ] Unmount or detach storage devices before firmware update where required.
- [ ] Disable runtime power management during update.
- [ ] Prevent suspend and shutdown during the critical stage.
- [ ] Handle progress reporting.
- [ ] Handle device reset and re-enumeration.
- [ ] Handle update timeout.
- [ ] Handle update rejection.
- [ ] Handle a device that disappears.
- [ ] Verify firmware version after reset.
- [ ] Run device self-test after update.
- [ ] Restore driver binding only after validation.
- [ ] Record complete audit receipt.
- [ ] Do not provide generic arbitrary-register firmware flashing.

### 153.5 Firmware update recovery and security

- [ ] Document motherboard vendor recovery mechanisms.
- [ ] Document dual-bank or fallback firmware capability.
- [ ] Create recovery media before motherboard firmware updates.
- [ ] Preserve BitLocker or other external-OS recovery implications in dual-boot documentation.
- [ ] Protect update packages from substitution.
- [ ] Protect update metadata from rollback.
- [ ] Use separate signing roles for metadata and payloads where practical.
- [ ] Support emergency revocation of a malicious updater plugin.
- [ ] Never download and execute firmware updates without explicit verification.
- [ ] Never treat TLS alone as firmware authenticity.
- [ ] Require physical confirmation for especially high-risk firmware updates if policy chooses it.
- [ ] Test power-loss behavior only on sacrificial hardware with known recovery capability.

## 154. Hardware Monitoring, Fans, Sensors, Chassis, and Watchdogs

### 154.1 Sensor framework

- [ ] Define sensor device objects.
- [ ] Define sensor channel objects.
- [ ] Define channel type.
- [ ] Define raw reading.
- [ ] Define scale.
- [ ] Define offset.
- [ ] Define unit.
- [ ] Define precision.
- [ ] Define sampling interval.
- [ ] Define validity state.
- [ ] Define stale-data state.
- [ ] Define minimum and maximum limits.
- [ ] Define warning and critical thresholds.
- [ ] Define hysteresis.
- [ ] Define alarm state.
- [ ] Define fault state.
- [ ] Define calibration metadata.
- [ ] Define source and trust level.
- [ ] Serialize controller access.
- [ ] Cache readings only within bounded age.
- [ ] Reject impossible values.
- [ ] Rate-limit sensor error logs.
- [ ] Expose readings through a stable user-space API.
- [ ] Restrict writable thresholds and controls.

### 154.2 Temperature, voltage, current, power, and fan monitoring

- [ ] Read CPU temperature through documented architectural or platform interfaces.
- [ ] Read per-die and per-package sensors where available.
- [ ] Read motherboard temperature sensors through chip-specific drivers.
- [ ] Read GPU temperature only through documented driver interfaces.
- [ ] Read NVMe composite and component temperatures.
- [ ] Read voltage rails only when scaling and channel identity are documented.
- [ ] Read current channels only when scaling is documented.
- [ ] Read power channels only when scaling and update interval are documented.
- [ ] Read fan tachometers.
- [ ] Detect stopped fans.
- [ ] Detect implausible tachometer values.
- [ ] Read PWM duty cycle.
- [ ] Change fan PWM only with an explicit supported controller driver.
- [ ] Preserve firmware automatic fan control by default.
- [ ] Do not seize fan control before a safe fallback curve exists.
- [ ] Restore firmware or hardware automatic control on driver exit, panic, suspend, and shutdown.
- [ ] Define minimum safe fan duty.
- [ ] Define emergency full-speed action.
- [ ] Validate thermal trip points against firmware and hardware limits.
- [ ] Never raise thermal shutdown limits.
- [ ] Never disable hardware overtemperature protection.
- [ ] Expose sensor source and uncertainty to the user.

### 154.3 Hardware watchdogs

- [ ] Discover ACPI watchdog tables when present.
- [ ] Discover PCI or Super I/O watchdogs only through supported drivers.
- [ ] Define watchdog timeout range.
- [ ] Define pretimeout support.
- [ ] Define reset type.
- [ ] Arm watchdog only after the responsible service is healthy.
- [ ] Refresh watchdog from an independent health authority.
- [ ] Prevent the monitored service from unilaterally hiding its own failure.
- [ ] Stop watchdog only when hardware and policy permit it.
- [ ] Handle nowayout-style policy if chosen.
- [ ] Record last watchdog reset reason.
- [ ] Distinguish watchdog reset from power loss.
- [ ] Test watchdog expiration on sacrificial test systems.
- [ ] Test boot-loop prevention after repeated watchdog resets.
- [ ] Integrate watchdog with safe-mode boot selection.

### 154.4 Storage, battery, chassis, and health integration

- [ ] Poll NVMe SMART and health log at a bounded interval.
- [ ] Report critical warning bits.
- [ ] Report media and data integrity errors.
- [ ] Report available spare and threshold.
- [ ] Report percentage used.
- [ ] Report unsafe shutdown count.
- [ ] Report temperature excursions.
- [ ] Report error log growth.
- [ ] Read battery state only through documented ACPI, EC, or device protocols.
- [ ] Report battery present and charging state.
- [ ] Report battery capacity and health when trustworthy.
- [ ] Detect chassis-intrusion events only when hardware exposes them.
- [ ] Record case-open events with privacy policy.
- [ ] Aggregate health status without hiding underlying raw evidence.
- [ ] Provide user notifications for actionable failures.
- [ ] Avoid alarming on transient or unsupported sensor values.
- [ ] Create a machine-readable health receipt.

## 155. Platform Firmware Boundaries, SMM, Security Coprocessors, and Runtime Services

- [ ] Document that System Management Mode executes outside ordinary kernel control.
- [ ] Document expected System Management Interrupt sources on the target platform where discoverable.
- [ ] Measure unexplained long interrupt-off or scheduling latencies that may be caused by firmware without claiming certainty.
- [ ] Do not attempt to map or modify SMRAM.
- [ ] Do not disable SMI sources without exact vendor documentation and a recovery plan.
- [ ] Treat firmware-owned thermal protection as authoritative.
- [ ] Treat firmware-owned voltage protection as authoritative.
- [ ] Treat firmware-owned fan fallback as authoritative.
- [ ] Document AMD Platform Security Processor boundaries on the target platform.
- [ ] Document firmware TPM implementation and update dependencies.
- [ ] Document management-engine or security-coprocessor boundaries on future platforms.
- [ ] Document motherboard baseboard-management controller interfaces if present.
- [ ] Do not expose undocumented mailbox commands to unprivileged software.
- [ ] Validate all shared-memory mailbox lengths and states.
- [ ] Apply timeouts to firmware mailbox calls.
- [ ] Serialize firmware mailbox calls when required.
- [ ] Handle firmware that never completes a request.
- [ ] Avoid calling UEFI runtime services from interrupt context unless explicitly safe.
- [ ] Serialize UEFI runtime services if firmware requires it.
- [ ] Preserve firmware-required virtual mappings.
- [ ] Handle SetVirtualAddressMap only according to UEFI requirements.
- [ ] Treat firmware return buffers as untrusted.
- [ ] Validate all firmware-provided pointers and sizes.
- [ ] Protect runtime-service code and data from user mappings.
- [ ] Record runtime-service failures.
- [ ] Provide a boot option to disable nonessential runtime-service use.
- [ ] Test firmware interfaces across warm reboot, cold boot, suspend, and resume.

## 156. Advanced Network Interfaces, Multicast, Virtual Links, and Traffic Control

### 156.1 Loopback, raw access, and packet capture

- [ ] Implement a loopback interface independent of physical NICs.
- [ ] Deliver loopback packets without unnecessary hardware checksums.
- [ ] Preserve normal routing and firewall semantics on loopback.
- [ ] Implement raw IPv4 sockets only for privileged or capability-authorized applications.
- [ ] Implement raw IPv6 sockets only for privileged or capability-authorized applications.
- [ ] Implement packet-level capture interface.
- [ ] Implement packet injection only under explicit privilege.
- [ ] Attach capture filters safely.
- [ ] Verify capture-filter bytecode or use a memory-safe filter representation.
- [ ] Prevent out-of-bounds packet reads in filters.
- [ ] Expose link-layer metadata and timestamps.
- [ ] Redact or restrict captures according to user and namespace boundaries.
- [ ] Provide promiscuous-mode control with privilege checks.
- [ ] Restore NIC filter state when capture clients exit.

### 156.2 IPv4 and IPv6 multicast

- [ ] Implement multicast address classification.
- [ ] Implement multicast route lookup.
- [ ] Implement socket multicast group membership.
- [ ] Implement per-interface membership.
- [ ] Implement source-specific membership only if targeted.
- [ ] Implement IPv4 IGMP host behavior for selected versions.
- [ ] Implement IPv6 MLD host behavior for selected versions.
- [ ] Suppress duplicate reports as required.
- [ ] Handle query timers.
- [ ] Handle unsolicited reports.
- [ ] Leave groups correctly.
- [ ] Program NIC multicast filters.
- [ ] Fall back to all-multicast only under explicit policy.
- [ ] Enforce namespace and permission boundaries.
- [ ] Implement multicast loopback option.
- [ ] Implement multicast TTL and hop-limit options.
- [ ] Test membership across interface up, down, and address changes.
- [ ] Test malformed IGMP and MLD packets.

### 156.3 VLANs, bridges, and link aggregation

- [ ] Implement 802.1Q VLAN tag parse and insertion only if in scope.
- [ ] Support VLAN ID validation.
- [ ] Support priority-code-point handling.
- [ ] Handle native and tagged traffic explicitly.
- [ ] Prevent VLAN-hopping through malformed or double-tagged frames.
- [ ] Implement software bridge forwarding database.
- [ ] Learn source MAC addresses.
- [ ] Age forwarding entries.
- [ ] Flood unknown unicast within policy.
- [ ] Handle broadcast and multicast forwarding.
- [ ] Prevent loops through spanning-tree support or explicit loop-free configuration requirements.
- [ ] Implement bridge port states.
- [ ] Apply firewall policy at clearly documented bridge hooks.
- [ ] Implement link aggregation only after exact mode and peer requirements are defined.
- [ ] Monitor member link state.
- [ ] Choose transmit member deterministically.
- [ ] Handle member addition and removal.
- [ ] Preserve flow ordering where required.
- [ ] Test failover and recovery.

### 156.4 Tunnels, VPN interfaces, and virtual network devices

- [ ] Define generic virtual-interface API.
- [ ] Implement point-to-point tunnel device abstraction.
- [ ] Implement TUN-style layer-3 user-space interface if required.
- [ ] Implement TAP-style layer-2 user-space interface if required.
- [ ] Enforce ownership and namespace boundaries.
- [ ] Validate packet sizes crossing user/kernel boundary.
- [ ] Support nonblocking I/O.
- [ ] Support multiqueue only after ordering semantics are defined.
- [ ] Implement IP-in-IP or GRE only if required.
- [ ] Implement UDP encapsulation only if required.
- [ ] Account encapsulation overhead in MTU.
- [ ] Prevent recursive tunnel loops.
- [ ] Implement PMTU handling for tunnels.
- [ ] Integrate VPN key storage with the secret service.
- [ ] Apply firewall policy before and after encapsulation at documented hooks.
- [ ] Provide a recovery path when VPN configuration blocks all networking.

### 156.5 Traffic control, QoS, and queue disciplines

- [ ] Define egress queue-discipline interface.
- [ ] Define ingress policing interface.
- [ ] Implement a simple FIFO queue discipline.
- [ ] Implement bounded queue length.
- [ ] Implement byte and packet limits.
- [ ] Implement fair queuing only after flow classification is defined.
- [ ] Implement active queue management only after controlled tests.
- [ ] Honor or rewrite DSCP only under policy.
- [ ] Support ECN without corrupting non-ECN traffic.
- [ ] Implement traffic shaping token buckets if required.
- [ ] Implement rate policing if required.
- [ ] Support per-interface and per-class statistics.
- [ ] Account drops by reason.
- [ ] Prevent unprivileged users from starving system traffic.
- [ ] Reserve control-plane traffic under overload if policy requires it.
- [ ] Integrate Wi-Fi hardware queues carefully.
- [ ] Test latency under saturation.
- [ ] Test packet reordering.
- [ ] Test queue reset on link down.

### 156.6 Network configuration control plane

- [ ] Define a versioned kernel-to-user network-control protocol.
- [ ] Support interface enumeration.
- [ ] Support address add and delete.
- [ ] Support route add and delete.
- [ ] Support neighbor add and delete.
- [ ] Support link up and down.
- [ ] Support MTU configuration.
- [ ] Support VLAN and bridge configuration if implemented.
- [ ] Support multicast membership diagnostics.
- [ ] Support firewall transaction updates.
- [ ] Support atomic configuration batches where required.
- [ ] Publish asynchronous link and address events.
- [ ] Publish route and neighbor events.
- [ ] Authenticate privileged operations.
- [ ] Validate every attribute length and type.
- [ ] Ignore unknown optional attributes safely.
- [ ] Reject unknown mandatory attributes.
- [ ] Fuzz all control-plane message decoders.

## 157. System IPC Bus, Name Services, Accounts, Directory, and Service Discovery

### 157.1 System and session message bus

- [ ] Define a local message-bus transport.
- [ ] Define system-bus instance.
- [ ] Define per-user session-bus instance.
- [ ] Authenticate peer credentials from the kernel rather than trusting self-reported identity.
- [ ] Define unique connection names.
- [ ] Define well-known service names.
- [ ] Define name ownership.
- [ ] Define name acquisition and release.
- [ ] Define service activation.
- [ ] Define method calls.
- [ ] Define method replies.
- [ ] Define errors.
- [ ] Define signals or events.
- [ ] Define properties.
- [ ] Define object paths or equivalent object identity.
- [ ] Define interface versions.
- [ ] Define message serial numbers.
- [ ] Define timeouts.
- [ ] Define cancellation.
- [ ] Define file-descriptor or handle passing.
- [ ] Define large-payload strategy.
- [ ] Set maximum message size.
- [ ] Set maximum nesting depth.
- [ ] Set maximum container element count.
- [ ] Validate message alignment and lengths.
- [ ] Apply per-name and per-method access control.
- [ ] Prevent a service from impersonating another service.
- [ ] Prevent activation loops.
- [ ] Prevent signal storms.
- [ ] Apply per-connection rate and memory limits.
- [ ] Provide introspection only to authorized callers where sensitive.
- [ ] Log denied privileged calls.
- [ ] Fuzz message parser and activation metadata.

### 157.2 Local account and group databases

- [ ] Define canonical user identifier range.
- [ ] Define canonical group identifier range.
- [ ] Reserve system user ranges.
- [ ] Reserve nobody or untrusted identity.
- [ ] Define username syntax.
- [ ] Define group-name syntax.
- [ ] Define local account database format.
- [ ] Define local group database format.
- [ ] Define protected password-verifier database.
- [ ] Set restrictive permissions on credential databases.
- [ ] Lock updates transactionally.
- [ ] Write updates atomically.
- [ ] Create backups before account-database replacement.
- [ ] Validate duplicate names and identifiers.
- [ ] Validate primary group existence.
- [ ] Validate home-directory path.
- [ ] Validate login shell path.
- [ ] Support locked accounts.
- [ ] Support expired accounts.
- [ ] Support password aging only if policy requires it.
- [ ] Record account creation, modification, and deletion.
- [ ] Prevent deletion of required system accounts.
- [ ] Remove or reassign resources deliberately when deleting users.

### 157.3 Name-service switch and directory integration

- [ ] Define lookup interfaces for users, groups, hosts, services, and protocols.
- [ ] Define ordered lookup sources.
- [ ] Define success, not-found, temporary-failure, and permanent-failure statuses.
- [ ] Prevent a remote directory outage from blocking critical local login indefinitely.
- [ ] Cache positive results with bounded TTL.
- [ ] Cache negative results with bounded TTL.
- [ ] Invalidate caches on local changes.
- [ ] Protect credential-bearing directory connections with authenticated encryption.
- [ ] Define offline-login policy.
- [ ] Protect cached offline credentials.
- [ ] Prevent identifier collisions across local and remote sources.
- [ ] Expose source attribution in diagnostics.
- [ ] Rate-limit repeated failed directory queries.
- [ ] Sandbox third-party directory plugins.

### 157.4 Local service discovery

- [ ] Define static service-name database.
- [ ] Define port-number database update process.
- [ ] Implement local hostname publication only under policy.
- [ ] Implement multicast DNS only if required.
- [ ] Implement DNS-based service discovery only if required.
- [ ] Validate advertised names and record sizes.
- [ ] Escape untrusted service metadata in user interfaces.
- [ ] Prevent service discovery from granting trust automatically.
- [ ] Separate discovery from authentication.
- [ ] Provide a privacy mode that suppresses unnecessary advertisements.
- [ ] Handle interface changes and sleep transitions.
- [ ] Rate-limit discovery traffic.

## 158. Scheduled Jobs, Maintenance Timers, and Periodic System Work

### 158.1 Job scheduler

- [ ] Define system jobs.
- [ ] Define per-user jobs.
- [ ] Define one-shot jobs.
- [ ] Define calendar jobs.
- [ ] Define monotonic interval jobs.
- [ ] Define boot-relative jobs.
- [ ] Define idle-triggered jobs only if required.
- [ ] Define path- or event-triggered jobs only if required.
- [ ] Define persistent jobs that run after missed deadlines.
- [ ] Define policy for jobs missed during shutdown or suspend.
- [ ] Define timezone for calendar schedules.
- [ ] Handle daylight-saving transitions.
- [ ] Handle wall-clock jumps.
- [ ] Handle leap-second policy consistently.
- [ ] Add randomized delay for fleet-scale network work where useful.
- [ ] Define concurrency policy per job.
- [ ] Prevent overlapping instances when prohibited.
- [ ] Define catch-up limits.
- [ ] Define execution timeout.
- [ ] Define retry policy.
- [ ] Define failure backoff.
- [ ] Define user, group, capabilities, and sandbox.
- [ ] Define environment and working directory.
- [ ] Define standard input, output, and error handling.
- [ ] Log start, completion, exit status, and runtime.
- [ ] Apply CPU, memory, I/O, and network limits.
- [ ] Prevent unprivileged users from creating privileged schedules.
- [ ] Validate schedule syntax.
- [ ] Provide a dry-run next-execution calculator.
- [ ] Test DST gaps and repeated hours.
- [ ] Test major backward and forward clock adjustments.

### 158.2 Required periodic maintenance jobs

- [ ] Schedule log rotation or retention enforcement.
- [ ] Schedule temporary-file cleanup.
- [ ] Schedule stale crash-dump cleanup under retention policy.
- [ ] Schedule package-metadata refresh only when networking and policy permit it.
- [ ] Schedule update checks without applying updates unexpectedly.
- [ ] Schedule certificate and trust-store freshness checks.
- [ ] Schedule timezone database freshness checks.
- [ ] Schedule Unicode and locale data updates through normal package management.
- [ ] Schedule filesystem scrub for filesystems that support it.
- [ ] Schedule RAID or mirror scrub when implemented.
- [ ] Schedule storage health polling.
- [ ] Schedule SSD discard only when continuous discard is not selected and device semantics are verified.
- [ ] Schedule backup jobs.
- [ ] Schedule snapshot pruning.
- [ ] Schedule package-cache pruning.
- [ ] Schedule orphaned-user-resource detection.
- [ ] Schedule account-expiry checks if policy uses them.
- [ ] Schedule security-policy validation.
- [ ] Schedule signing-certificate expiry warnings.
- [ ] Schedule benchmark baseline refresh only as an explicit research task.
- [ ] Do not schedule destructive optimization automatically.

### 158.3 Maintenance coordination

- [ ] Create a maintenance-inhibit API.
- [ ] Allow critical foreground work to delay nonessential maintenance within bounds.
- [ ] Prevent indefinite inhibition.
- [ ] Coordinate filesystem scrub with power and thermal state.
- [ ] Coordinate backups with snapshots and application quiesce hooks.
- [ ] Coordinate updates with backup and rollback availability.
- [ ] Coordinate package cleanup with active package transactions.
- [ ] Coordinate log rotation with logging daemon file handles.
- [ ] Coordinate certificate refresh with network time validity.
- [ ] Pause appropriate jobs on battery or metered networks when applicable.
- [ ] Resume jobs safely after reboot.
- [ ] Record skipped and deferred maintenance.
- [ ] Expose upcoming maintenance to the user.

## 159. Backup, Restore, Snapshots, Synchronization, and Data Migration

### 159.1 Backup policy and data classification

- [ ] Classify immutable operating-system data.
- [ ] Classify reproducible package data.
- [ ] Classify system configuration.
- [ ] Classify secrets and keys.
- [ ] Classify user documents.
- [ ] Classify application state.
- [ ] Classify caches.
- [ ] Classify logs.
- [ ] Classify benchmark receipts.
- [ ] Classify crash dumps.
- [ ] Define what is included by default.
- [ ] Define explicit exclusions.
- [ ] Define retention periods.
- [ ] Define recovery-point objective.
- [ ] Define recovery-time objective.
- [ ] Define local and off-device copy requirements.
- [ ] Define encryption requirements.
- [ ] Define who can restore each data class.
- [ ] Avoid backing up ephemeral secrets unnecessarily.
- [ ] Document data that cannot be reconstructed.

### 159.2 Snapshot and consistency infrastructure

- [ ] Define crash-consistent snapshot semantics.
- [ ] Define application-consistent snapshot semantics.
- [ ] Provide filesystem freeze and thaw hooks.
- [ ] Bound freeze duration.
- [ ] Flush required dirty data before snapshot according to semantics.
- [ ] Coordinate with databases through application hooks.
- [ ] Coordinate with virtual machines if implemented.
- [ ] Coordinate with package transactions.
- [ ] Coordinate with system updates.
- [ ] Create snapshots atomically where supported.
- [ ] Name snapshots uniquely.
- [ ] Record source filesystem identity and generation.
- [ ] Prevent snapshots from exhausting the source volume.
- [ ] Monitor copy-on-write space.
- [ ] Prune snapshots safely.
- [ ] Test snapshot creation under heavy writes.
- [ ] Test restore from snapshots after simulated crashes.

### 159.3 Backup engine

- [ ] Implement full backups.
- [ ] Implement incremental backups.
- [ ] Implement changed-file detection.
- [ ] Use content hashing where appropriate.
- [ ] Handle sparse files.
- [ ] Handle hard links.
- [ ] Handle symbolic links without path escape.
- [ ] Handle extended attributes.
- [ ] Handle ACLs.
- [ ] Handle security labels.
- [ ] Handle file capabilities.
- [ ] Handle device nodes only under system-backup policy.
- [ ] Handle open files according to snapshot semantics.
- [ ] Preserve ownership and timestamps where authorized.
- [ ] Chunk large files.
- [ ] Resume interrupted uploads safely.
- [ ] Compress data only when beneficial.
- [ ] Encrypt before untrusted transport or storage.
- [ ] Authenticate backup metadata.
- [ ] Authenticate backup data.
- [ ] Generate a manifest.
- [ ] Sign or MAC the manifest.
- [ ] Detect missing chunks.
- [ ] Detect corrupt chunks.
- [ ] Prevent path traversal during restore.
- [ ] Rate-limit resource use.
- [ ] Support bandwidth limits.
- [ ] Support removable-disk destinations.
- [ ] Support network destinations only through authenticated protocols.
- [ ] Never delete the last known-good backup during the same transaction that creates its replacement.

### 159.4 Restore and disaster recovery

- [ ] Provide file-level restore.
- [ ] Provide directory-level restore.
- [ ] Provide account-level restore.
- [ ] Provide system-configuration restore.
- [ ] Provide bare-metal restore plan.
- [ ] Provide restore into an alternate path for inspection.
- [ ] Verify backup integrity before destructive restore.
- [ ] Preview overwrite and deletion effects.
- [ ] Preserve the current state before large rollback when space permits.
- [ ] Restore metadata in a privilege-safe order.
- [ ] Do not allow restored symlinks to escape the destination root.
- [ ] Do not restore untrusted setuid, capability, or device-node metadata without policy.
- [ ] Handle identifier mapping when users differ.
- [ ] Handle filesystem-feature differences.
- [ ] Verify restored file hashes.
- [ ] Run application repair or migration hooks.
- [ ] Test recovery with the primary disk absent.
- [ ] Test recovery without network access.
- [ ] Test recovery from the oldest retained backup.
- [ ] Record restore receipt.

### 159.5 Synchronization and migration

- [ ] Distinguish synchronization from backup.
- [ ] Define conflict detection.
- [ ] Define conflict naming.
- [ ] Preserve both versions by default when conflict safety is uncertain.
- [ ] Use stable file identity where available.
- [ ] Handle renames.
- [ ] Handle case-sensitivity differences.
- [ ] Handle normalization differences.
- [ ] Handle forbidden filename differences.
- [ ] Handle clock skew without relying solely on modification time.
- [ ] Authenticate remote peers.
- [ ] Encrypt transport.
- [ ] Support pause and resume.
- [ ] Expose pending uploads and downloads.
- [ ] Provide account export.
- [ ] Provide account import.
- [ ] Provide application-data migration versioning.
- [ ] Provide cross-release configuration migration.
- [ ] Make every migration idempotent or journaled.
- [ ] Test interrupted migration and rollback.

## 160. GUI Toolkit, Clipboard, Drag-and-Drop, Portals, and Desktop IPC

### 160.1 Native GUI toolkit

- [ ] Define application event loop.
- [ ] Integrate file-descriptor readiness.
- [ ] Integrate timers.
- [ ] Integrate compositor events.
- [ ] Define window abstraction.
- [ ] Define surface abstraction.
- [ ] Define widget tree.
- [ ] Define layout engine.
- [ ] Define minimum, preferred, and maximum sizes.
- [ ] Define logical and physical coordinates.
- [ ] Support fractional scaling deliberately.
- [ ] Define theme tokens.
- [ ] Define font metrics.
- [ ] Define focus traversal.
- [ ] Define keyboard activation.
- [ ] Define pointer activation.
- [ ] Define touch activation if supported.
- [ ] Define disabled and read-only states.
- [ ] Define validation and error presentation.
- [ ] Define modal behavior without blocking the entire event loop.
- [ ] Define asynchronous dialogs.
- [ ] Define animation timing.
- [ ] Honor reduced-motion settings.
- [ ] Expose accessibility semantics for every widget.
- [ ] Provide deterministic screenshot tests.
- [ ] Fuzz rich-text and image inputs used by widgets.

### 160.2 Clipboard and selections

- [ ] Define clipboard ownership.
- [ ] Define primary-selection behavior only if desired.
- [ ] Define MIME or data-type negotiation.
- [ ] Stream large clipboard payloads.
- [ ] Set maximum metadata sizes.
- [ ] Handle owner exit.
- [ ] Handle delayed rendering.
- [ ] Sanitize rich-text formats in privileged consumers.
- [ ] Treat clipboard data as untrusted.
- [ ] Prevent background applications from reading clipboard without policy.
- [ ] Provide sensitive-clipboard timeout if desired.
- [ ] Clear secrets after paste only under user-visible policy.
- [ ] Prevent clipboard managers from retaining secrets without consent.
- [ ] Provide text normalization policy.
- [ ] Test binary, empty, huge, and malformed clipboard offers.

### 160.3 Drag and drop

- [ ] Define drag source.
- [ ] Define drag icon.
- [ ] Define drag target.
- [ ] Define offered data types.
- [ ] Define copy, move, link, and ask actions.
- [ ] Require target acceptance before transfer.
- [ ] Prevent source from writing arbitrary target paths.
- [ ] Use file-transfer portals for sandboxed applications.
- [ ] Confirm destructive move operations where needed.
- [ ] Handle source or target crash.
- [ ] Handle cancellation.
- [ ] Handle multi-file transfer.
- [ ] Handle cross-filesystem move as copy plus verified delete.
- [ ] Treat filenames and metadata as untrusted.
- [ ] Test drag across displays and scaling factors.

### 160.4 Desktop portals and privileged brokers

- [ ] Implement file-open portal.
- [ ] Implement file-save portal.
- [ ] Implement directory-selection portal.
- [ ] Implement URI-open portal.
- [ ] Implement notification portal.
- [ ] Implement print portal if printing exists.
- [ ] Implement screenshot portal.
- [ ] Implement screen-cast portal.
- [ ] Implement camera portal.
- [ ] Implement microphone portal.
- [ ] Implement secret-storage portal.
- [ ] Implement background-execution portal.
- [ ] Implement autostart portal.
- [ ] Implement power-inhibit portal.
- [ ] Implement settings portal.
- [ ] Bind every request to application identity.
- [ ] Display trusted system UI for permission grants.
- [ ] Prevent applications from drawing over trusted prompts.
- [ ] Return revocable handles instead of broad filesystem access where possible.
- [ ] Record sensitive grants.
- [ ] Allow persistent grants only with explicit user action.
- [ ] Handle broker restart.
- [ ] Version portal interfaces.

## 161. Accessibility and Assistive Technology

### 161.1 Accessibility architecture

- [ ] Define an accessibility object tree independent of visual rendering internals.
- [ ] Define stable object identity for the lifetime of exposed elements.
- [ ] Define roles.
- [ ] Define names.
- [ ] Define descriptions.
- [ ] Define states.
- [ ] Define values.
- [ ] Define actions.
- [ ] Define relations.
- [ ] Define bounds.
- [ ] Define text interfaces.
- [ ] Define selection interfaces.
- [ ] Define table interfaces.
- [ ] Define document interfaces.
- [ ] Define live-region events.
- [ ] Define focus events.
- [ ] Define property-change events.
- [ ] Define child-add and child-remove events.
- [ ] Protect sensitive fields from plaintext accessibility exposure.
- [ ] Authorize assistive-technology connections.
- [ ] Prevent ordinary applications from scraping other applications through the accessibility API.
- [ ] Rate-limit pathological event producers.
- [ ] Provide inspection and test tools.

### 161.2 Keyboard and motor accessibility

- [ ] Provide complete keyboard navigation for system UI.
- [ ] Provide visible focus indication.
- [ ] Provide predictable focus order.
- [ ] Provide keyboard shortcuts documentation.
- [ ] Provide sticky keys.
- [ ] Provide slow keys.
- [ ] Provide bounce keys.
- [ ] Provide mouse keys.
- [ ] Provide dwell click.
- [ ] Provide switch-access scanning framework if targeted.
- [ ] Provide configurable key repeat.
- [ ] Provide configurable double-click interval.
- [ ] Provide configurable pointer speed and acceleration.
- [ ] Provide larger pointer themes.
- [ ] Provide on-screen keyboard.
- [ ] Provide alternative input-device mapping.
- [ ] Ensure secure login supports required accessibility features without exposing credentials.

### 161.3 Visual accessibility

- [ ] Provide scalable text independent of display resolution.
- [ ] Provide scalable interface controls.
- [ ] Provide high-contrast themes.
- [ ] Provide dark and light themes without relying on color alone.
- [ ] Provide color filters where feasible.
- [ ] Provide color-blind-safe status indicators.
- [ ] Provide screen magnification.
- [ ] Provide full-screen and lens magnifier modes if targeted.
- [ ] Keep the magnified pointer and focus visible.
- [ ] Provide reduced transparency.
- [ ] Provide reduced motion.
- [ ] Avoid rapid flashes beyond defined safety limits.
- [ ] Support screen reader navigation of lock screen, installer, recovery, and settings.
- [ ] Provide text alternatives for nondecorative icons.

### 161.4 Screen reader, speech, captions, and braille

- [ ] Implement or port a screen reader.
- [ ] Provide speech-synthesis API.
- [ ] Provide voice selection.
- [ ] Provide speech rate, pitch, and volume control.
- [ ] Announce focus changes.
- [ ] Announce alerts without overwhelming the user.
- [ ] Support character, word, line, paragraph, and object navigation.
- [ ] Support editable text and selection feedback.
- [ ] Protect password contents.
- [ ] Provide braille-display transport and translation only if in scope.
- [ ] Provide refreshable braille routing-key support only if in scope.
- [ ] Provide speech-recognition input only with explicit microphone permission.
- [ ] Provide live captions only if media decoding and speech processing are supported.
- [ ] Expose application-provided captions.
- [ ] Expose audio-description tracks.
- [ ] Persist accessibility settings per user and at login where safe.

### 161.5 Accessibility validation

- [ ] Adopt documented accessibility acceptance criteria.
- [ ] Review relevant WCAG guidance for system web content and general interaction principles.
- [ ] Test every system screen with keyboard only.
- [ ] Test every system screen with the screen reader.
- [ ] Test at enlarged text and fractional scaling.
- [ ] Test high-contrast mode.
- [ ] Test reduced-motion mode.
- [ ] Test without audio.
- [ ] Test without color cues.
- [ ] Test timeout extension and cancellation.
- [ ] Test error recovery.
- [ ] Test installer and recovery environments.
- [ ] Include disabled users or qualified accessibility evaluators in release review.
- [ ] Track accessibility regressions as release-blocking defects according to severity.

## 162. Terminal Emulator, Virtual Consoles, and Console Session Details

### 162.1 Kernel virtual console

- [ ] Define virtual-console instances.
- [ ] Define active-console switching.
- [ ] Define console ownership during boot.
- [ ] Implement a text cell buffer.
- [ ] Implement glyph rendering through a pinned console font.
- [ ] Implement cursor rendering.
- [ ] Implement cursor visibility.
- [ ] Implement scrolling.
- [ ] Implement scrollback with bounded memory.
- [ ] Implement line wrapping.
- [ ] Implement tab stops.
- [ ] Implement backspace behavior.
- [ ] Implement carriage return.
- [ ] Implement line feed.
- [ ] Implement bell policy.
- [ ] Handle UTF-8 safely or explicitly limit early console to a smaller encoding.
- [ ] Represent unsupported glyphs clearly.
- [ ] Handle display-mode changes.
- [ ] Preserve panic console independent of user-space compositor.
- [ ] Implement keyboard input routing to the active console.
- [ ] Prevent unprivileged console switching across security boundaries.

### 162.2 Terminal-emulation parser

- [ ] Select the terminal control-sequence profile to support.
- [ ] Implement a finite-state parser for control characters.
- [ ] Implement escape sequences.
- [ ] Implement control-sequence introducer sequences.
- [ ] Implement operating-system command sequences only through an allowlist.
- [ ] Implement device-control strings only if required.
- [ ] Bound control-sequence length.
- [ ] Bound numeric parameter count.
- [ ] Handle malformed and truncated sequences.
- [ ] Implement cursor movement.
- [ ] Implement erase operations.
- [ ] Implement insert and delete characters.
- [ ] Implement insert and delete lines.
- [ ] Implement scrolling regions.
- [ ] Implement saved cursor state.
- [ ] Implement tab controls.
- [ ] Implement text attributes.
- [ ] Implement 16-color support.
- [ ] Implement 256-color support if targeted.
- [ ] Implement true color if targeted.
- [ ] Implement alternate-screen buffer.
- [ ] Implement bracketed paste mode.
- [ ] Implement focus events only when explicitly enabled.
- [ ] Implement mouse reporting only when explicitly enabled.
- [ ] Implement window-title changes with sanitization.
- [ ] Block title-based control-character injection.
- [ ] Implement hyperlinks only with confirmation and sanitization.
- [ ] Reject unsafe clipboard-control sequences by default.
- [ ] Treat terminal output as untrusted input to the parser.
- [ ] Fuzz the terminal parser continuously.

### 162.3 Terminal cell model and Unicode

- [ ] Store code points or grapheme clusters according to documented behavior.
- [ ] Track combining characters.
- [ ] Track wide characters.
- [ ] Handle zero-width characters.
- [ ] Handle ambiguous-width policy.
- [ ] Handle emoji sequences according to supported Unicode data.
- [ ] Prevent half of a wide character from remaining after edits.
- [ ] Preserve attributes across combining sequences.
- [ ] Handle bidirectional text policy explicitly.
- [ ] Avoid interpreting spoofed right-to-left controls in security prompts without isolation.
- [ ] Copy selected text in a predictable normalized form.
- [ ] Preserve line wrapping metadata for copy operations.

### 162.4 PTY integration and terminal application

- [ ] Allocate PTY master and slave safely.
- [ ] Assign controlling terminal.
- [ ] Propagate window-size changes.
- [ ] Generate terminal signals from configured control characters.
- [ ] Implement canonical and noncanonical modes.
- [ ] Implement echo modes.
- [ ] Implement input and output processing flags.
- [ ] Handle hangup when terminal closes.
- [ ] Handle child process exit.
- [ ] Integrate shell job control.
- [ ] Render through the compositor efficiently.
- [ ] Throttle producers that outrun rendering without deadlocking applications.
- [ ] Provide search in scrollback.
- [ ] Provide copy and paste through system clipboard policy.
- [ ] Provide font and scaling settings.
- [ ] Provide accessible terminal semantics.
- [ ] Protect pasted multiline commands with bracketed-paste handling and user cues.
- [ ] Test high-volume output.
- [ ] Test huge lines.
- [ ] Test rapid resize.
- [ ] Test malicious escape sequences.

## 163. File Events, Event Multiplexing, Asynchronous I/O, and Completion APIs

### 163.1 Descriptor readiness multiplexing

- [ ] Define readable readiness.
- [ ] Define writable readiness.
- [ ] Define priority or exceptional readiness if supported.
- [ ] Define hangup readiness.
- [ ] Define error readiness.
- [ ] Implement a simple select-compatible API if POSIX compatibility requires it.
- [ ] Implement poll-compatible API if POSIX compatibility requires it.
- [ ] Implement a scalable event-set API.
- [ ] Support level-triggered mode.
- [ ] Support edge-triggered mode only with precise drain semantics.
- [ ] Support one-shot registrations.
- [ ] Support add, modify, and delete operations.
- [ ] Handle duplicate registrations according to documented rules.
- [ ] Handle descriptor close racing with wait.
- [ ] Handle descriptor-number reuse without delivering stale events.
- [ ] Wake waiters on state transition.
- [ ] Prevent lost wakeups.
- [ ] Prevent thundering herd where practical.
- [ ] Support timeout with monotonic clock.
- [ ] Support signal-mask atomicity where required.
- [ ] Apply per-process limits to registered events.
- [ ] Test thousands and millions of descriptors at supported scales.

### 163.2 Event descriptors and kernel event sources

- [ ] Implement counter-based user event descriptor if useful.
- [ ] Implement timer event descriptor if useful.
- [ ] Implement signal event descriptor if useful.
- [ ] Implement process-exit event handle.
- [ ] Implement child-state event handle.
- [ ] Implement device hotplug event source.
- [ ] Implement network-link event source.
- [ ] Implement memory-pressure event source.
- [ ] Implement filesystem-change event source.
- [ ] Implement shutdown-notification event source.
- [ ] Ensure every event source has clear coalescing semantics.
- [ ] Ensure counter overflow is handled.
- [ ] Ensure close wakes or cancels waiters predictably.

### 163.3 Filesystem notification

- [ ] Define watch identity.
- [ ] Watch files.
- [ ] Watch directories.
- [ ] Report create events.
- [ ] Report delete events.
- [ ] Report rename source and destination with correlation.
- [ ] Report content modification.
- [ ] Report metadata modification.
- [ ] Report open and close only if required.
- [ ] Report mount and unmount where relevant.
- [ ] Handle watched-object deletion.
- [ ] Handle directory tree watches only with explicit resource accounting.
- [ ] Coalesce events without hiding required semantics.
- [ ] Report queue overflow explicitly.
- [ ] Apply permission checks when watch is created.
- [ ] Prevent watches from bypassing later access-control changes according to documented policy.
- [ ] Apply per-user watch limits.
- [ ] Test rename storms and recursive tree changes.

### 163.4 Asynchronous I/O and completion queues

- [ ] Define asynchronous request object.
- [ ] Define completion object.
- [ ] Define user data or cookie field.
- [ ] Define operation lifetime.
- [ ] Define cancellation semantics.
- [ ] Define timeout semantics.
- [ ] Define partial-completion semantics.
- [ ] Support asynchronous file read.
- [ ] Support asynchronous file write.
- [ ] Support asynchronous socket operations if targeted.
- [ ] Support vectored I/O.
- [ ] Support fsync and durability completions.
- [ ] Pin or copy user buffers safely.
- [ ] Bound pinned memory per process.
- [ ] Validate all submission entries before use.
- [ ] Prevent time-of-check/time-of-use changes to immutable request fields.
- [ ] Use generation counters for shared rings.
- [ ] Validate ring indices.
- [ ] Apply memory-ordering rules explicitly.
- [ ] Prevent kernel pointer exposure.
- [ ] Handle process exit with in-flight operations.
- [ ] Handle descriptor close with in-flight operations.
- [ ] Handle filesystem unmount with in-flight operations.
- [ ] Handle device reset and I/O cancellation.
- [ ] Test completion-queue overflow.
- [ ] Fuzz shared-ring interfaces.

## 164. Resource Limits, Quotas, Accounting, Reservations, and Pressure Signals

### 164.1 Process and user resource limits

- [ ] Limit address-space size.
- [ ] Limit resident memory where policy requires it.
- [ ] Limit locked memory.
- [ ] Limit stack size.
- [ ] Limit core-dump size.
- [ ] Limit CPU time.
- [ ] Limit open file descriptors.
- [ ] Limit processes or threads.
- [ ] Limit pending signals.
- [ ] Limit message-queue bytes.
- [ ] Limit file locks.
- [ ] Limit timer objects.
- [ ] Limit event registrations.
- [ ] Limit PTYs.
- [ ] Limit shared memory.
- [ ] Limit in-flight asynchronous I/O.
- [ ] Limit socket buffer memory.
- [ ] Limit packet-capture resources.
- [ ] Define soft and hard limits.
- [ ] Restrict who may raise hard limits.
- [ ] Inherit limits across process creation.
- [ ] Reset limits only through explicit API.
- [ ] Expose current limits.
- [ ] Test boundary and overflow cases.

### 164.2 Filesystem and storage quotas

- [ ] Implement per-user block quota if targeted.
- [ ] Implement per-group block quota if targeted.
- [ ] Implement per-project or application quota if targeted.
- [ ] Implement inode or object-count quota.
- [ ] Define soft quota.
- [ ] Define hard quota.
- [ ] Define grace period.
- [ ] Account sparse allocation accurately.
- [ ] Account copy-on-write sharing according to documented rules.
- [ ] Account snapshots according to documented rules.
- [ ] Account compression according to documented rules.
- [ ] Account delayed allocation.
- [ ] Reserve quota before dirtying data where necessary.
- [ ] Release quota on truncate and unlink at the correct durability stage.
- [ ] Recover quota state after crash.
- [ ] Provide quota check and repair tool.
- [ ] Provide user-visible remaining-space reporting.
- [ ] Prevent integer overflow in quota counters.

### 164.3 Service and application resource groups

- [ ] Create hierarchical resource groups.
- [ ] Assign processes atomically.
- [ ] Account CPU usage.
- [ ] Apply CPU shares or weights.
- [ ] Apply CPU bandwidth limits.
- [ ] Apply memory limits.
- [ ] Apply swap limits.
- [ ] Apply process-count limits.
- [ ] Apply I/O bandwidth or weight limits if supported.
- [ ] Apply network classification or limits if supported.
- [ ] Track descendants.
- [ ] Define behavior on group deletion.
- [ ] Define behavior on OOM within a group.
- [ ] Provide pressure events.
- [ ] Prevent child groups from escaping parent limits.
- [ ] Prevent unprivileged delegation from gaining privilege.
- [ ] Integrate groups with service manager.
- [ ] Integrate groups with application sandbox.
- [ ] Expose historical usage summaries.

### 164.4 Process accounting and observability

- [ ] Record process start time.
- [ ] Record process exit time.
- [ ] Record exit status and terminating signal.
- [ ] Record user and system CPU time.
- [ ] Record peak resident memory.
- [ ] Record page faults.
- [ ] Record bytes read and written.
- [ ] Record network bytes only if attribution is reliable.
- [ ] Record context switches.
- [ ] Record scheduler wait time.
- [ ] Record resource-group identity.
- [ ] Record executable identity and build ID.
- [ ] Protect accounting logs from tampering.
- [ ] Apply retention and privacy policy.
- [ ] Avoid excessive overhead.
- [ ] Expose live usage through stable APIs.

## 165. Removable Media, SD/eMMC, Optical, Type-C, USB4, Thunderbolt, and Other Optional Buses

### 165.1 Removable-media policy

- [ ] Define automatic discovery behavior.
- [ ] Define automatic mount behavior.
- [ ] Disable automatic execution from removable media.
- [ ] Assign removable-media ownership to the active authorized session.
- [ ] Apply filesystem trust and mount-option policy.
- [ ] Sanitize volume labels in user interfaces.
- [ ] Handle duplicate filesystem identifiers.
- [ ] Handle surprise removal.
- [ ] Flush safely before eject.
- [ ] Expose safe-eject operation.
- [ ] Prevent unmount while files are in use unless forced policy is explicit.
- [ ] Notify applications of removal.
- [ ] Scan or quarantine untrusted content only under transparent policy.
- [ ] Respect encrypted removable media.
- [ ] Record device identity with privacy safeguards.

### 165.2 SD, SDIO, and eMMC

- [ ] Obtain host-controller and card specifications required for implementation.
- [ ] Discover PCI or ACPI SD host controller.
- [ ] Reset host controller.
- [ ] Configure bus power.
- [ ] Configure clock.
- [ ] Configure bus width.
- [ ] Send card-identification commands.
- [ ] Handle card insertion and removal.
- [ ] Read card registers.
- [ ] Negotiate voltage and speed modes conservatively.
- [ ] Implement block read.
- [ ] Implement block write.
- [ ] Implement erase and discard only when semantics are verified.
- [ ] Handle write protection.
- [ ] Handle CRC and timeout errors.
- [ ] Handle tuning for high-speed modes only after basic modes are stable.
- [ ] Implement eMMC partitions only if in scope.
- [ ] Implement eMMC reliable write and cache flush correctly.
- [ ] Do not expose eMMC boot-partition writes to ordinary applications.
- [ ] Support SDIO functions only through device-specific drivers.
- [ ] Test power loss and surprise removal.

### 165.3 Optical and legacy removable storage

- [ ] Decide whether optical media is supported.
- [ ] Implement ATAPI packet transport only if optical support is selected.
- [ ] Read media and track information.
- [ ] Support read-only ISO-style filesystem only if required.
- [ ] Treat optical writing as a separate high-risk subsystem.
- [ ] Handle no media.
- [ ] Handle tray open and close.
- [ ] Handle media change.
- [ ] Handle read errors and retries without indefinite stalls.
- [ ] Decide whether floppy controllers are explicitly unsupported.
- [ ] Decide whether parallel ports are explicitly unsupported.
- [ ] Decide whether FireWire is explicitly unsupported.
- [ ] Document all omitted legacy transports.

### 165.4 USB Type-C and Power Delivery

- [ ] Separate USB data-role support from Type-C connector policy.
- [ ] Discover Type-C port controllers through documented firmware and bus interfaces.
- [ ] Track attach and detach.
- [ ] Track orientation.
- [ ] Track source and sink power roles.
- [ ] Track host and device data roles.
- [ ] Negotiate only power profiles supported by hardware and platform policy.
- [ ] Never request unsafe voltage or current.
- [ ] Handle role swap only when supported.
- [ ] Handle alternate modes only with exact specifications and drivers.
- [ ] Coordinate DisplayPort alternate mode with display driver.
- [ ] Coordinate USB4 tunneling only after IOMMU and authorization are mature.
- [ ] Expose cable and power information accurately.
- [ ] Recover from controller reset.
- [ ] Test malformed and rapid attach sequences with certified test equipment.

### 165.5 USB4 and Thunderbolt security

- [ ] Decide whether USB4 or Thunderbolt tunneling is in scope.
- [ ] Require IOMMU DMA isolation before authorizing tunneled PCIe.
- [ ] Enumerate routers and tunnels through documented interfaces.
- [ ] Implement device authorization policy.
- [ ] Support user confirmation for new external PCIe devices.
- [ ] Bind authorization to stable device identity when available.
- [ ] Handle identity spoofing risk.
- [ ] Restrict preboot DMA.
- [ ] Restrict devices while the screen is locked according to policy.
- [ ] Revoke tunnels on detach.
- [ ] Handle surprise removal of tunneled PCIe devices.
- [ ] Audit authorization decisions.
- [ ] Provide a mode that disables PCIe tunneling while retaining ordinary USB where hardware permits.
- [ ] Test DMA isolation with hostile-device test tooling.

## 166. Storage Volume Management, RAID, Device Mapping, Loop Devices, and Multipath

### 166.1 Generic stacked block devices

- [ ] Define block-device stacking rules.
- [ ] Prevent stacking cycles.
- [ ] Propagate logical and physical block sizes.
- [ ] Propagate maximum transfer size.
- [ ] Propagate discard capability.
- [ ] Propagate flush and force-unit-access semantics.
- [ ] Propagate write-zeroes semantics.
- [ ] Propagate read-only state.
- [ ] Propagate rotational and latency hints only when trustworthy.
- [ ] Translate I/O offsets without overflow.
- [ ] Split requests at child-device boundaries.
- [ ] Aggregate completion status.
- [ ] Handle partial child failure.
- [ ] Freeze stacked devices for topology changes.
- [ ] Record complete dependency graph.

### 166.2 Loop and image-backed devices

- [ ] Create block device backed by a regular file.
- [ ] Prevent recursive loop-device backing.
- [ ] Validate offset and size.
- [ ] Support read-only mode.
- [ ] Support direct-I/O mode only when alignment permits.
- [ ] Flush through to backing file.
- [ ] Propagate errors.
- [ ] Handle backing-file truncation.
- [ ] Prevent unprivileged use from bypassing filesystem permissions.
- [ ] Detach only after users release the device or through explicit forced policy.
- [ ] Support sparse image files safely.
- [ ] Test nested filesystem images under power loss.

### 166.3 Software RAID

- [ ] Decide supported RAID levels.
- [ ] Define superblock metadata format.
- [ ] Version metadata.
- [ ] Identify member devices uniquely.
- [ ] Record array UUID.
- [ ] Record member role and generation.
- [ ] Assemble arrays deterministically.
- [ ] Reject stale or foreign members by default.
- [ ] Implement degraded read behavior.
- [ ] Implement degraded write behavior only for supported levels.
- [ ] Implement rebuild.
- [ ] Persist rebuild position.
- [ ] Throttle rebuild.
- [ ] Scrub data and parity.
- [ ] Report mismatch counts.
- [ ] Handle member failure.
- [ ] Handle replacement member.
- [ ] Handle write hole through journaling, bitmap, or equivalent design where applicable.
- [ ] Propagate flushes to all required members.
- [ ] Test power loss during metadata update and rebuild.
- [ ] Prevent automatic destructive reinitialization.

### 166.4 Logical volumes, snapshots, and thin provisioning

- [ ] Define volume metadata format.
- [ ] Replicate critical metadata.
- [ ] Journal metadata updates.
- [ ] Create physical-volume identifiers.
- [ ] Create volume groups or equivalent pools.
- [ ] Create logical volumes.
- [ ] Resize volumes safely.
- [ ] Create read-only snapshots.
- [ ] Create writable snapshots only after copy-on-write semantics are complete.
- [ ] Track changed extents.
- [ ] Handle snapshot space exhaustion explicitly.
- [ ] Implement thin allocation only after metadata crash consistency is proven.
- [ ] Implement discard mapping.
- [ ] Prevent data leakage when reallocating blocks between volumes.
- [ ] Provide metadata backup and restore.
- [ ] Provide offline repair tooling.
- [ ] Test interrupted resize and snapshot merge.

### 166.5 Multipath storage

- [ ] Identify multiple paths to the same logical device reliably.
- [ ] Avoid merging unrelated devices with similar metadata.
- [ ] Choose active path.
- [ ] Monitor path health.
- [ ] Fail over in-flight and future I/O according to transport guarantees.
- [ ] Avoid duplicate writes after ambiguous timeout.
- [ ] Restore failed paths cautiously.
- [ ] Implement path-priority policy only when documented.
- [ ] Expose path state.
- [ ] Test cable pull and controller reset.
- [ ] Do not enable multipath automatically on consumer devices without identity confidence.

## 167. User Data Model, Home Directories, MIME Types, File Associations, and Session State

- [ ] Define per-user home-directory layout.
- [ ] Define desktop, documents, downloads, music, pictures, videos, templates, and public directories only if the desktop uses them.
- [ ] Define per-user configuration directory.
- [ ] Define per-user persistent data directory.
- [ ] Define per-user cache directory.
- [ ] Define per-user runtime directory.
- [ ] Set permissions for every directory class.
- [ ] Create runtime directory on login and remove it on logout or reboot.
- [ ] Prevent symlink attacks during home initialization.
- [ ] Version default user skeleton files.
- [ ] Migrate user configuration transactionally.
- [ ] Define MIME-type database format.
- [ ] Detect file types by content and extension with clear precedence.
- [ ] Treat file content as untrusted regardless of extension.
- [ ] Define application desktop-entry or launcher metadata.
- [ ] Validate launch metadata.
- [ ] Define default application selection.
- [ ] Define per-user overrides.
- [ ] Define file-open confirmation for executable or high-risk types.
- [ ] Define recent-document storage and privacy controls.
- [ ] Define bookmarks.
- [ ] Define trash semantics.
- [ ] Keep trash on the same filesystem where practical.
- [ ] Define trash size and retention limits.
- [ ] Handle secure deletion claims honestly; do not promise physical erasure on flash storage.
- [ ] Define removable-volume mount points.
- [ ] Define user-visible filesystem names.
- [ ] Define session restore policy.
- [ ] Do not restore privileged or crashed applications blindly.
- [ ] Provide user data export in documented formats.
- [ ] Provide account deletion and data-retention workflow.

## 168. System Integrity Maintenance, Self-Checks, Drift Detection, and Health Service

### 168.1 Boot and image integrity checks

- [ ] Verify bootloader signature or measured identity.
- [ ] Verify kernel signature.
- [ ] Verify initramfs signature or hash.
- [ ] Verify immutable system-image signature or root hash.
- [ ] Verify package database consistency.
- [ ] Verify required boot files exist.
- [ ] Verify boot-entry targets exist.
- [ ] Verify previous-known-good image exists.
- [ ] Verify recovery image exists.
- [ ] Verify free space for rollback.
- [ ] Verify active and pending update states are coherent.
- [ ] Detect interrupted update transactions.
- [ ] Detect repeated boot failures.
- [ ] Mark boot successful only after required health milestones.
- [ ] Enter safe mode after configured failure threshold.

### 168.2 Filesystem and data integrity maintenance

- [ ] Schedule metadata consistency checks where required.
- [ ] Schedule checksum scrub where supported.
- [ ] Verify redundant copies.
- [ ] Repair only when a trustworthy copy exists.
- [ ] Quarantine unrecoverable corrupt files.
- [ ] Report exact affected paths or object identifiers.
- [ ] Preserve corrupt evidence before repair where possible.
- [ ] Check free-space accounting.
- [ ] Check quota accounting.
- [ ] Check snapshot metadata.
- [ ] Check encryption metadata.
- [ ] Check backup catalog integrity.
- [ ] Check receipt-store integrity.
- [ ] Test repair tools on copies before production use.
- [ ] Never auto-repair ambiguous corruption destructively.

### 168.3 Package, configuration, and security drift

- [ ] Verify installed package hashes.
- [ ] Verify package signatures and provenance references.
- [ ] Detect modified immutable files.
- [ ] Detect unexpected privileged executables.
- [ ] Detect unexpected setuid, setgid, capability, or security-label changes.
- [ ] Detect unauthorized kernel modules.
- [ ] Detect unauthorized startup services.
- [ ] Detect policy-file changes.
- [ ] Detect trust-store changes.
- [ ] Detect signing-key changes.
- [ ] Detect firewall drift.
- [ ] Detect account and group drift.
- [ ] Detect permission drift on secrets.
- [ ] Distinguish approved local configuration from compromise.
- [ ] Provide remediation preview.
- [ ] Require explicit authorization for destructive remediation.
- [ ] Record a signed integrity report.

### 168.4 Health daemon and user notification

- [ ] Run the health daemon with read-only access wherever possible.
- [ ] Aggregate boot, storage, memory, thermal, network, update, backup, and security health.
- [ ] Preserve subsystem-specific severity and evidence.
- [ ] Avoid collapsing unknown state into healthy state.
- [ ] Define healthy, degraded, failed, and unknown states.
- [ ] Deduplicate repeated alerts.
- [ ] Rate-limit notifications.
- [ ] Escalate persistent critical failures.
- [ ] Provide command-line and graphical status.
- [ ] Provide machine-readable status.
- [ ] Provide exact remediation steps.
- [ ] Never claim an issue is repaired without verification.
- [ ] Record health transitions.
- [ ] Include health summary in support bundles.

### 168.5 Periodic self-test suite

- [ ] Run allocator consistency checks in diagnostic builds.
- [ ] Run scheduler watchdog checks.
- [ ] Run timer monotonicity checks.
- [ ] Run clock-synchronization checks.
- [ ] Run random-number-generator health checks.
- [ ] Run storage flush-semantics probes only on dedicated test volumes.
- [ ] Run network loopback tests.
- [ ] Run DNS and time-source reachability tests without treating internet outage as OS corruption.
- [ ] Run certificate-expiry checks.
- [ ] Run update-channel signature checks.
- [ ] Run recovery-image boot test in CI.
- [ ] Run backup restore sampling.
- [ ] Run PDC watchdog and rollback drills.
- [ ] Record test version, inputs, outputs, and timestamps.
- [ ] Keep self-tests bounded to avoid degrading normal workloads.

## 169. Supplemental Official Reference Register

- [ ] Review the NXP I2C-bus specification and user manual UM10204 Revision 7.0 or its current superseding revision: https://www.nxp.com/documents/user_manual/UM10204.pdf
- [ ] Review SMBus Specification 3.3.1 or its current superseding revision: https://www.smbus.org/specs/
- [ ] Review ACPI embedded-controller, GPIO, serial-bus, SPCR, DBG2, and UEFI-variable requirements in the current ACPI and UEFI specifications: https://uefi.org/specifications
- [ ] Review the current IEEE 802.1 standards and project register for VLANs, bridging, access control, and time-sensitive networking: https://1.ieee802.org/
- [ ] Review IGMPv3 in RFC 3376 if IPv4 multicast is implemented: https://datatracker.ietf.org/doc/rfc3376/
- [ ] Review MLDv2 in RFC 3810 if IPv6 multicast is implemented: https://datatracker.ietf.org/doc/rfc3810/
- [ ] Review differentiated services architecture in RFC 2475 if DSCP policy is implemented: https://datatracker.ietf.org/doc/rfc2475/
- [ ] Review Explicit Congestion Notification in RFC 3168 and applicable updates if ECN is implemented: https://datatracker.ietf.org/doc/rfc3168/
- [ ] Review ECMA-48 terminal control functions if VT-style terminal compatibility is implemented: https://ecma-international.org/publications-and-standards/standards/ecma-48/
- [ ] Review WCAG 2.2 and current W3C accessibility guidance for system web content and interaction design: https://www.w3.org/WAI/standards-guidelines/wcag/
- [ ] Review WAI-ARIA only as applicable to web-based PooleOS interfaces: https://www.w3.org/WAI/standards-guidelines/aria/
- [ ] Review the SD Association simplified specifications and obtain required normative specifications before SD or eMMC implementation: https://www.sdcard.org/downloads/pls/
- [ ] Review USB Type-C, USB Power Delivery, USB4, and related specifications before implementing connector policy or tunneling: https://www.usb.org/documents
- [ ] Review processor-vendor microcode update guidance for the exact processor family before implementing runtime microcode loading.
- [ ] Review motherboard-vendor firmware recovery and capsule documentation for the exact board revision before any production firmware updater is enabled.

## 170. Final Reality Checks

- [ ] Treat a booting kernel as the beginning, not completion, of an operating system.
- [ ] Treat every device driver as a security boundary and failure domain.
- [ ] Treat every parser as attacker-controlled unless input authenticity and format are guaranteed.
- [ ] Treat every storage optimization as invalid until durability equivalence survives power loss.
- [ ] Treat every performance result as invalid until required outputs are equivalent.
- [ ] Treat every PDC speedup as workload-bounded until independently reproduced across additional hardware.
- [ ] Treat firmware and hardware documentation gaps as explicit blockers, not invitations to guess register behavior.
- [ ] Keep the recovery path simpler than the normal path.
- [ ] Keep the safe scheduler independent from the experimental scheduler.
- [ ] Keep the GOP framebuffer path independent from the native GPU driver.
- [ ] Keep package and update verification independent from network transport security.
- [ ] Keep rollback independent from the component being rolled back.
- [ ] Keep watchdog authority independent from the planner and actuator.
- [ ] Keep signing roots offline.
- [ ] Keep raw data and negative results.
- [ ] Do not promote a component merely because its happy path works.
- [ ] Do not mark daily-driver readiness while data-loss, boot-loop, privilege, or recovery defects remain.
- [ ] Do not publish compatibility claims without exact hardware identifiers and evidence.
- [ ] Do not publish security claims without threat model and test evidence.
- [ ] Do not publish standards-conformance claims without the applicable conformance process.
- [ ] Do not call PooleOS from-scratch merely because the kernel is original; publish the exact provenance of every ported library, firmware blob, data table, tool, and protocol implementation.
- [ ] Do not permit experimental PDC mechanisms to control boot, recovery, thermal safety, key storage, or update trust roots.
- [ ] Do not test undocumented firmware flashing, voltage, clock, fan, or security-coprocessor commands on primary hardware.
- [ ] Do not treat passing emulation as proof of real-hardware correctness.
- [ ] Do not treat a single successful real-hardware boot as stability.
- [ ] Do not treat filesystem mount success as crash consistency.
- [ ] Do not treat encrypted transport as authenticated software provenance.
- [ ] Do not treat a signed component as safe merely because the key is trusted.
- [ ] Do not treat an unavailable sensor as a healthy reading.
- [ ] Do not silently continue when integrity cannot be established.
