param(
    [Parameter(Mandatory=$true)][string]$Identity,
    [Parameter(Mandatory=$true)][string]$Name,
    [Parameter(Mandatory=$true)][string]$Config,
    [Parameter(Mandatory=$true)][string]$Runtime,
    [Parameter(Mandatory=$true)][ValidateRange(-96,96)][int]$Dx,
    [Parameter(Mandatory=$true)][ValidateRange(-96,96)][int]$Dy,
    [Parameter(Mandatory=$true)][ValidateRange(0,1)][int]$Left,
    [Parameter(Mandatory=$true)][ValidateRange(0,95)][int]$Sequence
)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$locked = $false
$session = $null
$result = $null
try {
    if ($Identity -cnotmatch '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$' -or
        $Name -cne "PooleOS-Preview-$Identity") { throw 'Invalid owned identity' }
    $configPath = [IO.Path]::GetFullPath($Config)
    $runtimePath = [IO.Path]::GetFullPath($Runtime)
    # Reject a different COM registration before instantiating either class.
    $registrations = @(
        @('VirtualBox.VirtualBox','{B1A7A4F2-47B9-4A1E-82B2-07CCD5323C3F}','LocalServer32','VBoxSVC.exe'),
        @('VirtualBox.Session','{3C02F46D-C9D2-4F11-A384-53F0CF917214}','InprocServer32','VBoxC.dll')
    )
    foreach ($entry in $registrations) {
        $id = (Get-Item -LiteralPath "Registry::HKEY_CLASSES_ROOT\$($entry[0])\CLSID").GetValue('')
        if ($id -cne $entry[1]) { throw 'COM class identity changed' }
        $server = (Get-Item -LiteralPath "Registry::HKEY_CLASSES_ROOT\CLSID\$id\$($entry[2])").GetValue('')
        $expected = Join-Path $runtimePath $entry[3]
        if ($entry[2] -eq 'LocalServer32') { $expected = '"' + $expected + '"' }
        if ($server -ine $expected) { throw 'COM runtime path changed' }
    }
    $box = New-Object -ComObject VirtualBox.VirtualBox
    $machine = $box.FindMachine($Identity)
    function Assert-Owned($vm) {
        if ($vm.Id -cne $Identity -or $vm.Name -cne $Name -or
            [IO.Path]::GetFullPath($vm.SettingsFilePath) -ine $configPath -or
            [int]$vm.State -ne 6) { throw 'Owned running VM identity differs' }
    }
    Assert-Owned $machine
    $session = New-Object -ComObject VirtualBox.Session
    $machine.LockMachine($session, 1) # SDK LockType_Shared, never a settings/write lock.
    $locked = $true
    Assert-Owned $session.Machine
    $mouse = $session.Console.Mouse
    if (-not $mouse.RelativeSupported) { throw 'Relative pointing unsupported' }
    $mouse.PutMouseEvent($Dx, $Dy, 0, 0, $Left)
    $result = @{identity=$Identity; sequence=$Sequence; dx=$Dx; dy=$Dy; left=$Left; relative=$true}
} catch {
    $result = @{error=$_.Exception.Message}
} finally {
    if ($locked) {
        try {
            $session.UnlockMachine()
            if ([int]$session.State -ne 1) { throw 'Session unlock unconfirmed' }
            if (-not $result.ContainsKey('error')) { $result.unlocked = $true }
        } catch { $result = @{error=$_.Exception.Message} }
    }
}
$result | ConvertTo-Json -Compress
if ($result.ContainsKey('error')) { exit 1 }
