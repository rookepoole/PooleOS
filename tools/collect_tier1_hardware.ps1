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
    schema_version = "1.0"
    artifact_kind = "pooleos_tier1_hardware_private_capture"
    collected_at_utc = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ")
    collection_mode = "read_only"
    collector = [ordered]@{ version = "1.0.0"; script_sha256 = $collectorHash }
    mutation_guard = [ordered]@{
        firmware_write = $false
        disk_write = $false
        tpm_write = $false
        boot_configuration_write = $false
        device_configuration_write = $false
        power_action = $false
        stress_load = $false
    }
    privacy_guard = [ordered]@{
        serial_numbers_collected = $false
        mac_addresses_collected = $false
        uuids_collected = $false
        full_pnp_instance_paths_collected = $false
        user_or_host_names_collected = $false
        tpm_ek_or_certificate_material_collected = $false
        raw_firmware_table_bytes_retained = $false
    }
    host_context = [ordered]@{
        architecture = [System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString()
        firmware_type = [ordered]@{ status = $firmwareTypeStatus; value = $firmwareType }
        hypervisor_present = if ($computerSystems.Count -gt 0) { [bool]$computerSystems[0].hypervisor_present } else { $false }
    }
    security = [ordered]@{ secure_boot = $secureBoot; tpm = $tpm }
    system = [ordered]@{ baseboard = $boards; bios = $bios; computer_system = $computerSystems }
    processor = $processors
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
Write-Host ("wrote {0}: mode=read_only pnp={1} acpi={2} raw_tables=false identifiers=false" -f $destination, $pnp.Count, $acpiIds.Count)
