param(
    [string]$ToolchainRoot = (Join-Path (Split-Path -Parent $PSScriptRoot) ".toolchains\native-models")
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repositoryRoot = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$allowedToolchainParent = [IO.Path]::GetFullPath((Join-Path $repositoryRoot ".toolchains"))
$ToolchainRoot = [IO.Path]::GetFullPath($ToolchainRoot)
$allowedPrefix = $allowedToolchainParent + [IO.Path]::DirectorySeparatorChar
if (-not $ToolchainRoot.StartsWith($allowedPrefix, [StringComparison]::OrdinalIgnoreCase)) {
    throw "model toolchain root must remain below the repository .toolchains directory"
}

$jreName = "OpenJDK21U-jre_x64_windows_hotspot_21.0.11_10.zip"
$jreUrl = "https://github.com/adoptium/temurin21-binaries/releases/download/jdk-21.0.11%2B10/$jreName"
$jreSha256 = "BE26677AAA20B39A62EDCAAB4C8857A8B76673B0F45ABC0B6143B142B62717E4"
$signatureUrl = "$jreUrl.sig"
$signatureSha256 = "DD49A01A70180BEE61CFCCA91C6DB84DD49095E3C3D86A6AC5DCE69D4BCF68C1"
$tlcUrl = "https://github.com/tlaplus/tlaplus/releases/download/v1.7.4/tla2tools.jar"
$tlcSha1 = "BEE4A54F3EE3D4AFC347C3240EC2D9E93B075104"
$tlcSha256 = "936A262061C914694DFD669A543BE24573C45D5AA0FF20A8B96B23D01E050E88"

$downloads = Join-Path $ToolchainRoot "downloads"
$runtime = Join-Path $ToolchainRoot "runtime"
$jreArchive = Join-Path $downloads $jreName
$signature = "$jreArchive.sig"
$tlcJar = Join-Path $downloads "tla2tools-v1.7.4.jar"
$java = Join-Path $runtime "jdk-21.0.11+10-jre\bin\java.exe"

New-Item -ItemType Directory -Force $downloads, $runtime | Out-Null

$pathToCheck = $ToolchainRoot
while ($true) {
    $item = Get-Item -LiteralPath $pathToCheck -Force
    if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw "model toolchain directory chain contains a reparse point"
    }
    if ($item.FullName.Equals($allowedToolchainParent, [StringComparison]::OrdinalIgnoreCase)) {
        break
    }
    $pathToCheck = [IO.Directory]::GetParent($item.FullName).FullName
}
foreach ($directory in @($downloads, $runtime)) {
    $item = Get-Item -LiteralPath $directory -Force
    if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw "model toolchain data directory contains a reparse point"
    }
}

function Get-LockedFile {
    param([string]$Url, [string]$Path, [string]$Sha256)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        Invoke-WebRequest -UseBasicParsing -Uri $Url -OutFile $Path
    }
    $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash
    if ($actual -ne $Sha256) {
        throw "SHA-256 mismatch for $([IO.Path]::GetFileName($Path))"
    }
}

Get-LockedFile -Url $jreUrl -Path $jreArchive -Sha256 $jreSha256
Get-LockedFile -Url $signatureUrl -Path $signature -Sha256 $signatureSha256
Get-LockedFile -Url $tlcUrl -Path $tlcJar -Sha256 $tlcSha256

if ((Get-FileHash -Algorithm SHA1 -LiteralPath $tlcJar).Hash -ne $tlcSha1) {
    throw "published TLC SHA-1 mismatch"
}

if (-not (Test-Path -LiteralPath $java -PathType Leaf)) {
    if (Get-ChildItem -LiteralPath $runtime -Force | Select-Object -First 1) {
        throw "JRE runtime directory is nonempty but the locked java.exe is absent"
    }
    Expand-Archive -LiteralPath $jreArchive -DestinationPath $runtime
}

$javaHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $java).Hash
if ($javaHash -ne "5E0FAB9F07952CEB6E71EB9FD33E1ED69959904CA00CF70869B7BAF516A98016") {
    throw "locked java.exe SHA-256 mismatch"
}

& $java -version
if ($LASTEXITCODE -ne 0) {
    throw "locked Java runtime failed its version probe"
}
Write-Output "NATIVE_MODEL_TOOLCHAIN_READY root=$ToolchainRoot global_install=false path_mutation=false"
