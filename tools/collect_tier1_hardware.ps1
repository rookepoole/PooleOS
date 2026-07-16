[CmdletBinding()]
param(
    [string]$Out = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

if ([string]::IsNullOrWhiteSpace($Out)) {
    $Out = Join-Path (Split-Path -Parent $PSCommandPath) "..\runs\tier1_hardware_capture.private.json"
}

if (-not $Out.EndsWith(".private.json", [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "The capture output must end with .private.json"
}

Add-Type -TypeDefinition @"
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;

public static class PooleFirmwareTables {
    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern uint EnumSystemFirmwareTables(uint provider, IntPtr buffer, uint size);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern uint GetSystemFirmwareTable(uint provider, uint tableId, IntPtr buffer, uint size);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool GetFirmwareType(out uint firmwareType);

    public static uint Provider(string text) {
        byte[] bytes = System.Text.Encoding.ASCII.GetBytes(text);
        if (bytes.Length != 4) throw new ArgumentException("provider must be four ASCII bytes");
        return ((uint)bytes[0] << 24) | ((uint)bytes[1] << 16) | ((uint)bytes[2] << 8) | bytes[3];
    }

    public static uint[] Enumerate(string text) {
        uint provider = Provider(text);
        uint needed = EnumSystemFirmwareTables(provider, IntPtr.Zero, 0);
        if (needed == 0) return new uint[0];
        IntPtr buffer = Marshal.AllocHGlobal((int)needed);
        try {
            uint written = EnumSystemFirmwareTables(provider, buffer, needed);
            if (written == 0 || written > needed || written % 4 != 0) return new uint[0];
            uint[] values = new uint[written / 4];
            for (int i = 0; i < values.Length; i++) values[i] = unchecked((uint)Marshal.ReadInt32(buffer, i * 4));
            return values;
        } finally { Marshal.FreeHGlobal(buffer); }
    }

    public static byte[] Read(string text, uint tableId) {
        uint provider = Provider(text);
        uint needed = GetSystemFirmwareTable(provider, tableId, IntPtr.Zero, 0);
        if (needed == 0) return new byte[0];
        IntPtr buffer = Marshal.AllocHGlobal((int)needed);
        try {
            uint written = GetSystemFirmwareTable(provider, tableId, buffer, needed);
            if (written == 0 || written > needed) return new byte[0];
            byte[] data = new byte[written];
            Marshal.Copy(buffer, data, 0, (int)written);
            return data;
        } finally { Marshal.FreeHGlobal(buffer); }
    }

    public static string Signature(uint value) {
        return System.Text.Encoding.ASCII.GetString(BitConverter.GetBytes(value));
    }

    public static string FirmwareType() {
        uint value;
        if (!GetFirmwareType(out value)) return "Unavailable";
        if (value == 1) return "BIOS";
        if (value == 2) return "UEFI";
        return "Unknown";
    }
}

public static class PooleCpuidProbe {
    [UnmanagedFunctionPointer(CallingConvention.Winapi)]
    private delegate void CpuidThunk(uint leaf, uint subleaf, IntPtr output);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern IntPtr VirtualAlloc(IntPtr address, UIntPtr size, uint allocationType, uint protection);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool VirtualProtect(IntPtr address, UIntPtr size, uint newProtection, out uint oldProtection);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern IntPtr GetCurrentProcess();

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool GetProcessAffinityMask(IntPtr process, out UIntPtr processMask, out UIntPtr systemMask);

    [DllImport("kernel32.dll")]
    private static extern IntPtr GetCurrentThread();

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern UIntPtr SetThreadAffinityMask(IntPtr thread, UIntPtr affinityMask);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool FlushInstructionCache(IntPtr process, IntPtr address, UIntPtr size);

    private static readonly UIntPtr QueryAffinityMask = GetLowestProcessAffinityMask();
    private static readonly CpuidThunk Probe = CreateProbe();

    private static UIntPtr GetLowestProcessAffinityMask() {
        UIntPtr processMask;
        UIntPtr systemMask;
        if (!GetProcessAffinityMask(GetCurrentProcess(), out processMask, out systemMask)) {
            throw new Win32Exception(Marshal.GetLastWin32Error(), "GetProcessAffinityMask failed");
        }
        ulong mask = processMask.ToUInt64();
        if (mask == 0) throw new InvalidOperationException("process affinity mask is empty");
        return new UIntPtr(mask & (~mask + 1UL));
    }

    private static CpuidThunk CreateProbe() {
        if (!Environment.Is64BitProcess) throw new PlatformNotSupportedException("x86-64 process required");

        // Preserve nonvolatile RBX, execute CPUID(EAX=ECX, ECX=EDX), and write EAX/EBX/ECX/EDX to R8.
        byte[] code = new byte[] {
            0x53, 0x8B, 0xC1, 0x8B, 0xCA, 0x0F, 0xA2,
            0x41, 0x89, 0x00, 0x41, 0x89, 0x58, 0x04,
            0x41, 0x89, 0x48, 0x08, 0x41, 0x89, 0x50, 0x0C,
            0x5B, 0xC3
        };
        UIntPtr size = new UIntPtr((uint)code.Length);
        IntPtr memory = VirtualAlloc(IntPtr.Zero, size, 0x3000, 0x04);
        if (memory == IntPtr.Zero) throw new Win32Exception(Marshal.GetLastWin32Error(), "VirtualAlloc failed");
        Marshal.Copy(code, 0, memory, code.Length);
        uint oldProtection;
        if (!VirtualProtect(memory, size, 0x20, out oldProtection)) {
            throw new Win32Exception(Marshal.GetLastWin32Error(), "VirtualProtect failed");
        }
        if (!FlushInstructionCache(GetCurrentProcess(), memory, size)) {
            throw new Win32Exception(Marshal.GetLastWin32Error(), "FlushInstructionCache failed");
        }
        return (CpuidThunk)Marshal.GetDelegateForFunctionPointer(memory, typeof(CpuidThunk));
    }

    public static uint[] Query(uint leaf, uint subleaf) {
        IntPtr output = Marshal.AllocHGlobal(16);
        IntPtr thread = GetCurrentThread();
        UIntPtr previousAffinity = UIntPtr.Zero;
        try {
            previousAffinity = SetThreadAffinityMask(thread, QueryAffinityMask);
            if (previousAffinity == UIntPtr.Zero) {
                throw new Win32Exception(Marshal.GetLastWin32Error(), "SetThreadAffinityMask failed");
            }
            Probe(leaf, subleaf, output);
            return new uint[] {
                unchecked((uint)Marshal.ReadInt32(output, 0)),
                unchecked((uint)Marshal.ReadInt32(output, 4)),
                unchecked((uint)Marshal.ReadInt32(output, 8)),
                unchecked((uint)Marshal.ReadInt32(output, 12))
            };
        } finally {
            Marshal.FreeHGlobal(output);
            if (previousAffinity != UIntPtr.Zero && SetThreadAffinityMask(thread, previousAffinity) == UIntPtr.Zero) {
                throw new Win32Exception(Marshal.GetLastWin32Error(), "restoring thread affinity failed");
            }
        }
    }
}
"@

function Get-Sha256Bytes([byte[]]$Data) {
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($sha.ComputeHash($Data))).Replace("-", "") }
    finally { $sha.Dispose() }
}

function Get-HardwarePrefix([string]$PnpDeviceId) {
    if ([string]::IsNullOrWhiteSpace($PnpDeviceId)) { return "" }
    $parts = $PnpDeviceId -split "\\"
    if ($parts.Count -lt 2) { return $parts[0].Trim() }
    return ("{0}\{1}" -f $parts[0].Trim(), $parts[1].Trim())
}

function Convert-MonitorText($Value) {
    if ($null -eq $Value) { return "" }
    return -join @($Value | Where-Object { $_ -ne 0 } | ForEach-Object { [char]$_ })
}

function Format-Hex32([uint32]$Value) {
    return ("0x{0:X8}" -f [uint64]$Value)
}

function Read-CpuidRecord([uint32]$Leaf, [uint32]$Subleaf) {
    $values = [PooleCpuidProbe]::Query($Leaf, $Subleaf)
    $record = [ordered]@{
        leaf = Format-Hex32 $Leaf
        subleaf = Format-Hex32 $Subleaf
        eax = Format-Hex32 $values[0]
        ebx = Format-Hex32 $values[1]
        ecx = Format-Hex32 $values[2]
        edx = Format-Hex32 $values[3]
    }
    return [ordered]@{ values = $values; record = $record }
}

$collectorHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $PSCommandPath).Hash
$collectorErrors = [System.Collections.Generic.List[object]]::new()

function Get-CimRecords([string]$ClassName, [string]$Namespace = "root\cimv2") {
    try { return @(Get-CimInstance -Namespace $Namespace -ClassName $ClassName -ErrorAction Stop) }
    catch {
        $collectorErrors.Add([ordered]@{ channel = $ClassName; status = "unavailable"; error_type = $_.Exception.GetType().Name })
        return @()
    }
}

$boards = @(Get-CimRecords "Win32_BaseBoard" | ForEach-Object {
    [ordered]@{ manufacturer = [string]$_.Manufacturer; product = [string]$_.Product; version = [string]$_.Version }
})
$bios = @(Get-CimRecords "Win32_BIOS" | ForEach-Object {
    $date = if ($null -ne $_.ReleaseDate) { $_.ReleaseDate.ToUniversalTime().ToString("yyyy-MM-dd") } else { "" }
    [ordered]@{
        manufacturer = [string]$_.Manufacturer
        version = [string]$_.SMBIOSBIOSVersion
        smbios_version = ("{0}.{1}" -f $_.SMBIOSMajorVersion, $_.SMBIOSMinorVersion)
        release_date_utc = $date
    }
})
$computerSystems = @(Get-CimRecords "Win32_ComputerSystem" | ForEach-Object {
    [ordered]@{ hypervisor_present = [bool]$_.HypervisorPresent; total_physical_memory_bytes = [uint64]$_.TotalPhysicalMemory }
})
$processors = @(Get-CimRecords "Win32_Processor" | ForEach-Object {
    [ordered]@{
        name = ([string]$_.Name).Trim()
        manufacturer = [string]$_.Manufacturer
        cim_family_code = [int]$_.Family
        cim_stepping = [string]$_.Stepping
        cim_revision = [int]$_.Revision
        core_count = [int]$_.NumberOfCores
        logical_processor_count = [int]$_.NumberOfLogicalProcessors
        socket = [string]$_.SocketDesignation
        virtualization_firmware_enabled = [bool]$_.VirtualizationFirmwareEnabled
        slat_reported = [bool]$_.SecondLevelAddressTranslationExtensions
    }
})

$cpuidRecords = [System.Collections.Generic.List[object]]::new()
$cpuidStatus = "unavailable"
$cpuidMaxBasicLeaf = "0x00000000"
$cpuidMaxExtendedLeaf = "0x00000000"
try {
    $basic0 = Read-CpuidRecord 0 0
    $cpuidRecords.Add($basic0.record)
    [uint32]$maxBasic = $basic0.values[0]
    $cpuidMaxBasicLeaf = Format-Hex32 $maxBasic

    if ($maxBasic -ge 1) {
        $cpuidRecords.Add((Read-CpuidRecord 1 0).record)
    }
    if ($maxBasic -ge 7) {
        $structured0 = Read-CpuidRecord 7 0
        $cpuidRecords.Add($structured0.record)
        $maxStructuredSubleaf = [Math]::Min([int]$structured0.values[0], 2)
        for ($subleaf = 1; $subleaf -le $maxStructuredSubleaf; $subleaf++) {
            $cpuidRecords.Add((Read-CpuidRecord 7 ([uint32]$subleaf)).record)
        }
    }
    if ($maxBasic -ge 0x0B) {
        for ($subleaf = 0; $subleaf -le 7; $subleaf++) {
            $topology = Read-CpuidRecord 0x0B ([uint32]$subleaf)
            $cpuidRecords.Add($topology.record)
            $levelType = ([uint32]$topology.values[2] -shr 8) -band 0xFF
            if ($levelType -eq 0) { break }
        }
    }
    if ($maxBasic -ge 0x0D) {
        $cpuidRecords.Add((Read-CpuidRecord 0x0D 0).record)
        $cpuidRecords.Add((Read-CpuidRecord 0x0D 1).record)
    }

    $extended0 = Read-CpuidRecord ([uint32]0x80000000L) 0
    $cpuidRecords.Add($extended0.record)
    [uint32]$maxExtended = $extended0.values[0]
    $cpuidMaxExtendedLeaf = Format-Hex32 $maxExtended
    foreach ($leaf in @(0x80000001L, 0x80000007L, 0x80000008L, 0x8000000AL, 0x8000001EL, 0x8000001FL)) {
        if ([uint64]$maxExtended -ge [uint64]$leaf) {
            $cpuidRecords.Add((Read-CpuidRecord ([uint32]$leaf) 0).record)
        }
    }
    $cpuidStatus = if ($cpuidRecords.Count -gt 0) { "observed" } else { "unavailable" }
} catch {
    $collectorErrors.Add([ordered]@{ channel = "CPU_CPUID"; status = "unavailable"; error_type = $_.Exception.GetType().Name })
}
$memory = @(Get-CimRecords "Win32_PhysicalMemory" | ForEach-Object {
    [ordered]@{
        manufacturer = ([string]$_.Manufacturer).Trim()
        part_number = ([string]$_.PartNumber).Trim()
        capacity_bytes = [uint64]$_.Capacity
        rated_speed_mt_s = [int]$_.Speed
        configured_speed_mt_s = [int]$_.ConfiguredClockSpeed
        device_locator = [string]$_.DeviceLocator
        bank_label = [string]$_.BankLabel
    }
})
$storage = @(Get-CimRecords "Win32_DiskDrive" | ForEach-Object {
    [ordered]@{
        model = ([string]$_.Model).Trim()
        firmware_revision = ([string]$_.FirmwareRevision).Trim()
        size_bytes = [uint64]$_.Size
        interface_type = [string]$_.InterfaceType
        hardware_prefix = Get-HardwarePrefix ([string]$_.PNPDeviceID)
    }
})
$display = @(Get-CimRecords "Win32_VideoController" | ForEach-Object {
    [ordered]@{
        name = ([string]$_.Name).Trim()
        horizontal_resolution = [int]$_.CurrentHorizontalResolution
        vertical_resolution = [int]$_.CurrentVerticalResolution
        hardware_prefix = Get-HardwarePrefix ([string]$_.PNPDeviceID)
    }
})
$network = @(Get-CimRecords "Win32_NetworkAdapter" | Where-Object { $_.PhysicalAdapter } | ForEach-Object {
    [ordered]@{
        name = ([string]$_.Name).Trim()
        manufacturer = ([string]$_.Manufacturer).Trim()
        current_link_speed_bps = [uint64]$_.Speed
        hardware_prefix = Get-HardwarePrefix ([string]$_.PNPDeviceID)
    }
})
$pnp = @(Get-CimRecords "Win32_PnPEntity" | Where-Object { -not [string]::IsNullOrWhiteSpace($_.PNPDeviceID) } | ForEach-Object {
    [ordered]@{
        name = ([string]$_.Name).Trim()
        class_guid = [string]$_.ClassGuid
        hardware_prefix = Get-HardwarePrefix ([string]$_.PNPDeviceID)
        status = [string]$_.Status
    }
})

$monitorStatus = "unavailable"
$monitors = @()
try {
    $monitors = @(Get-CimInstance -Namespace "root\wmi" -ClassName "WmiMonitorID" -ErrorAction Stop | ForEach-Object {
        [ordered]@{
            manufacturer = Convert-MonitorText $_.ManufacturerName
            friendly_name = Convert-MonitorText $_.UserFriendlyName
            manufacture_week = [int]$_.WeekOfManufacture
            manufacture_year = [int]$_.YearOfManufacture
        }
    })
    $monitorStatus = if ($monitors.Count -gt 0) { "observed" } else { "unavailable" }
} catch {
    $collectorErrors.Add([ordered]@{ channel = "WmiMonitorID"; status = "unavailable"; error_type = $_.Exception.GetType().Name })
}

$firmwareType = [PooleFirmwareTables]::FirmwareType()
$firmwareTypeStatus = if ($firmwareType -eq "Unavailable") { "unavailable" } else { "observed" }
$secureBoot = [ordered]@{ status = "unavailable"; value = $null; error_type = "none" }
try {
    $secureBoot.value = [bool](Confirm-SecureBootUEFI -ErrorAction Stop)
    $secureBoot.status = "observed"
} catch {
    $secureBoot.status = if ($_.Exception -is [System.UnauthorizedAccessException]) { "permission_limited" } else { "unavailable" }
    $secureBoot.error_type = $_.Exception.GetType().Name
}

$tpm = [ordered]@{ status = "unavailable"; present = $null; enabled = $null; activated = $null; error_type = "none" }
try {
    $tpmRecord = Get-CimInstance -Namespace "root\cimv2\security\microsofttpm" -ClassName "Win32_Tpm" -ErrorAction Stop | Select-Object -First 1
    if ($null -ne $tpmRecord) {
        $tpm.status = "observed"
        $tpm.present = $true
        $tpm.enabled = [bool]$tpmRecord.IsEnabled_InitialValue
        $tpm.activated = [bool]$tpmRecord.IsActivated_InitialValue
    }
} catch {
    $isAccessDenied = ($_.Exception -is [System.UnauthorizedAccessException])
    if ($_.Exception -is [Microsoft.Management.Infrastructure.CimException]) {
        $isAccessDenied = $isAccessDenied -or ([int]$_.Exception.NativeErrorCode -eq 2)
    }
    $tpm.status = if ($isAccessDenied) { "permission_limited" } else { "unavailable" }
    $tpm.error_type = $_.Exception.GetType().Name
}

$acpiTables = @()
$acpiStatus = "unavailable"
$acpiIds = @([PooleFirmwareTables]::Enumerate("ACPI"))
if ($acpiIds.Count -gt 0) {
    $acpiStatus = "observed"
    $acpiTables = @($acpiIds | Sort-Object -Unique | ForEach-Object {
        $bytes = [PooleFirmwareTables]::Read("ACPI", [uint32]$_)
        [ordered]@{
            signature = [PooleFirmwareTables]::Signature([uint32]$_)
            byte_count = $bytes.Length
            sha256 = if ($bytes.Length -gt 0) { Get-Sha256Bytes $bytes } else { "" }
        }
    })
}
$smbiosBytes = [PooleFirmwareTables]::Read("RSMB", 0)
$smbios = [ordered]@{
    status = if ($smbiosBytes.Length -gt 0) { "observed" } else { "unavailable" }
    byte_count = $smbiosBytes.Length
    sha256 = if ($smbiosBytes.Length -gt 0) { Get-Sha256Bytes $smbiosBytes } else { "" }
}

$temperatureCount = @(Get-CimRecords "Win32_TemperatureProbe").Count
$batteryCount = @(Get-CimRecords "Win32_Battery").Count
$upsCount = @(Get-CimRecords "Win32_UninterruptiblePowerSupply").Count
$sensorStatus = if (($temperatureCount + $batteryCount + $upsCount) -gt 0) { "partial" } else { "unavailable" }

$capture = [ordered]@{
    schema_version = "1.1"
    artifact_kind = "pooleos_tier1_hardware_private_capture"
    collected_at_utc = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ")
    collection_mode = "read_only"
    collector = [ordered]@{ version = "1.1.0"; script_sha256 = $collectorHash }
    mutation_guard = [ordered]@{
        firmware_write = $false
        disk_write = $false
        tpm_write = $false
        boot_configuration_write = $false
        device_configuration_write = $false
        power_action = $false
        stress_load = $false
    }
    privileged_probe_guard = [ordered]@{
        kernel_driver_loaded = $false
        kernel_device_opened = $false
        physical_memory_mapped = $false
        io_ports_accessed = $false
        msr_read_attempted = $false
        msr_write_attempted = $false
        pci_config_read_attempted = $false
        pci_config_write_attempted = $false
        spd_bus_access_attempted = $false
        uefi_variable_read_attempted = $false
        uefi_variable_write_attempted = $false
    }
    privacy_guard = [ordered]@{
        serial_numbers_collected = $false
        mac_addresses_collected = $false
        uuids_collected = $false
        full_pnp_instance_paths_collected = $false
        user_or_host_names_collected = $false
        tpm_ek_or_certificate_material_collected = $false
        raw_firmware_table_bytes_retained = $false
        cpuid_processor_serial_leaf_collected = $false
    }
    host_context = [ordered]@{
        architecture = [System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString()
        firmware_type = [ordered]@{ status = $firmwareTypeStatus; value = $firmwareType }
        hypervisor_present = if ($computerSystems.Count -gt 0) { [bool]$computerSystems[0].hypervisor_present } else { $false }
    }
    security = [ordered]@{ secure_boot = $secureBoot; tpm = $tpm }
    system = [ordered]@{ baseboard = $boards; bios = $bios; computer_system = $computerSystems }
    processor = $processors
    cpu_architecture = [ordered]@{
        status = if ($cpuidStatus -eq "observed") { "partial_cpuid_observed_msr_pending" } else { "unavailable" }
        cpuid = [ordered]@{
            status = $cpuidStatus
            execution_mode = "unprivileged_user_mode"
            affinity_policy = "lowest_process_allowed_logical_processor_restored_per_query"
            allowlist_id = "POOLEOS-CPUID-ALLOWLIST-1"
            record_count = $cpuidRecords.Count
            max_basic_leaf = $cpuidMaxBasicLeaf
            max_extended_leaf = $cpuidMaxExtendedLeaf
            processor_serial_leaf_collected = $false
            records = @($cpuidRecords)
        }
        msr = [ordered]@{
            status = "pending_reviewed_privileged_mechanism"
            access_attempted = $false
            driver_loaded = $false
            device_opened = $false
            write_attempted = $false
        }
    }
    memory = $memory
    storage = $storage
    display = $display
    network = $network
    pnp_devices = $pnp
    monitor = [ordered]@{ status = $monitorStatus; records = $monitors; serial_field_collected = $false }
    firmware_tables = [ordered]@{
        acpi = [ordered]@{ status = $acpiStatus; enumerated_signature_count = $acpiIds.Count; tables = $acpiTables; duplicate_signature_reads_complete = $false }
        smbios = $smbios
    }
    sensors_power = [ordered]@{
        status = $sensorStatus
        temperature_probe_count = $temperatureCount
        battery_count = $batteryCount
        ups_count = $upsCount
        active_probe_performed = $false
    }
    collector_errors = @($collectorErrors)
}

$destination = [IO.Path]::GetFullPath($Out)
[IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($destination)) | Out-Null
$json = $capture | ConvertTo-Json -Depth 12
[IO.File]::WriteAllText($destination, $json + "`n", [Text.UTF8Encoding]::new($false))
Write-Host ("wrote {0}: mode=read_only pnp={1} acpi={2} cpuid={3} msr=pending raw_tables=false identifiers=false" -f $destination, $pnp.Count, $acpiIds.Count, $cpuidRecords.Count)
