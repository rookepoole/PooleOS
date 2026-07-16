param(
    [string]$ToolchainRoot = "",
    [switch]$ForceDownload
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if ([string]::IsNullOrWhiteSpace($ToolchainRoot)) {
    $ToolchainRoot = Join-Path $RepoRoot ".toolchains\rust-1.97.0"
}
$ToolchainRoot = [System.IO.Path]::GetFullPath($ToolchainRoot)
$LockPath = Join-Path $RepoRoot "specs\native-toolchain-lock.json"
$Lock = Get-Content -LiteralPath $LockPath -Raw | ConvertFrom-Json
$DownloadRoot = Join-Path $ToolchainRoot "downloads"
$RustupHome = Join-Path $ToolchainRoot "rustup"
$CargoHome = Join-Path $ToolchainRoot "cargo"
$InstallerPath = Join-Path $DownloadRoot "rustup-init.exe"
$ManifestPath = Join-Path $DownloadRoot "channel-rust-1.97.0.toml"
$ManifestHashPath = Join-Path $DownloadRoot "channel-rust-1.97.0.toml.sha256"
$InstallerHashPath = Join-Path $DownloadRoot "rustup-init.exe.sha256"

New-Item -ItemType Directory -Force -Path $DownloadRoot, $RustupHome, $CargoHome | Out-Null

function Get-Sha256([string]$Path) {
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToUpperInvariant()
}

function Get-PinnedFile(
    [string]$Url,
    [string]$Path,
    [string]$ExpectedSha256
) {
    if ($ForceDownload -or -not (Test-Path -LiteralPath $Path)) {
        Invoke-WebRequest -Uri $Url -OutFile $Path -UseBasicParsing
    }
    $Actual = Get-Sha256 $Path
    if ($Actual -ne $ExpectedSha256.ToUpperInvariant()) {
        throw "SHA-256 mismatch for $([System.IO.Path]::GetFileName($Path)): expected $ExpectedSha256, got $Actual"
    }
}

Get-PinnedFile $Lock.rustup_init.url $InstallerPath $Lock.rustup_init.sha256
Get-PinnedFile $Lock.channel_manifest.url $ManifestPath $Lock.channel_manifest.sha256

Invoke-WebRequest -Uri $Lock.rustup_init.sha256_url -OutFile $InstallerHashPath -UseBasicParsing
$OfficialInstallerHash = ((Get-Content -LiteralPath $InstallerHashPath -Raw).Trim() -split '\s+')[0].ToUpperInvariant()
if ($OfficialInstallerHash -ne $Lock.rustup_init.sha256) {
    throw "Official rustup-init hash record does not match the lock"
}

Invoke-WebRequest -Uri $Lock.channel_manifest.sha256_url -OutFile $ManifestHashPath -UseBasicParsing
$OfficialManifestHash = ((Get-Content -LiteralPath $ManifestHashPath -Raw).Trim() -split '\s+')[0].ToUpperInvariant()
if ($OfficialManifestHash -ne $Lock.channel_manifest.sha256) {
    throw "Official channel-manifest hash record does not match the lock"
}

$env:RUSTUP_HOME = $RustupHome
$env:CARGO_HOME = $CargoHome
$env:RUSTUP_DIST_SERVER = "https://static.rust-lang.org"
$env:RUSTUP_UPDATE_ROOT = "https://static.rust-lang.org/rustup"

$Rustup = Join-Path $CargoHome "bin\rustup.exe"
if (-not (Test-Path -LiteralPath $Rustup)) {
    & $InstallerPath -y --no-modify-path --profile minimal --default-toolchain none
    if ($LASTEXITCODE -ne 0) {
        throw "rustup-init failed with exit code $LASTEXITCODE"
    }
}
if (-not (Test-Path -LiteralPath $Rustup)) {
    throw "verified rustup installer did not create the workspace-local rustup executable"
}
if ((Get-Sha256 $Rustup) -ne $Lock.rustup_init.sha256) {
    throw "workspace-local rustup proxy does not match the verified rustup-init executable"
}
& $Rustup set profile minimal
if ($LASTEXITCODE -ne 0) {
    throw "rustup profile selection failed with exit code $LASTEXITCODE"
}
& $Rustup toolchain install $Lock.toolchain.channel --profile minimal --no-self-update
if ($LASTEXITCODE -ne 0) {
    throw "pinned Rust toolchain installation failed with exit code $LASTEXITCODE"
}
foreach ($Target in @("x86_64-unknown-uefi", "x86_64-unknown-none")) {
    & $Rustup target add --toolchain $Lock.toolchain.channel $Target
    if ($LASTEXITCODE -ne 0) {
        throw "target installation failed for $Target with exit code $LASTEXITCODE"
    }
}

$InstalledTargets = @(& $Rustup target list --installed --toolchain $Lock.toolchain.channel)
foreach ($Target in @("x86_64-unknown-uefi", "x86_64-unknown-none")) {
    if ($Target -notin $InstalledTargets) {
        throw "required target is not installed: $Target"
    }
}

& $Rustup run $Lock.toolchain.channel rustc --version --verbose
if ($LASTEXITCODE -ne 0) {
    throw "rustc verification failed with exit code $LASTEXITCODE"
}
& $Rustup run $Lock.toolchain.channel cargo --version --verbose
if ($LASTEXITCODE -ne 0) {
    throw "cargo verification failed with exit code $LASTEXITCODE"
}
Write-Output "POOLEOS_NATIVE_TOOLCHAIN_READY channel=$($Lock.toolchain.channel) targets=$($InstalledTargets -join ',') global_path_mutated=false"
