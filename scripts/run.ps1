param(
    [ValidateSet('health','verify','serve','status','generate','research')][string]$Action='health',
    [string]$Spec,[string]$Job,
    [ValidateSet('status','run','report')][string]$ResearchAction='run',
    [switch]$Once,[switch]$LiveWrites
)
$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
$projectRoot=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
if($Action -eq 'generate'){
    if(-not $Spec -or -not $Job){throw '-Action generate requires -Spec and -Job'}
    if(-not [IO.Path]::IsPathRooted($Spec)){$Spec=Join-Path $projectRoot $Spec}
    $Spec=(Resolve-Path -LiteralPath $Spec).Path
}
$env:PYTHONUTF8='1'
$env:PYTHONPATH=Join-Path $projectRoot 'src'
$env:LUOMU_CAD_ROOT=$projectRoot
$env:LUOMU_CAD_LIVE_WRITES=if ($LiveWrites) {'1'} else {'0'}
$env:UV_PROJECT_ENVIRONMENT=Join-Path $projectRoot '.venv'
$python=Join-Path $env:UV_PROJECT_ENVIRONMENT 'Scripts\python.exe'
$command=Get-Command uv -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
$uv=if($command){$command.Source}else{Join-Path $projectRoot 'runtime\uv\uv.exe'}
if(-not(Test-Path -LiteralPath $uv)){
    $directory=Split-Path $uv
    New-Item -ItemType Directory -Force -Path $directory | Out-Null
    $base='https://github.com/astral-sh/uv/releases/download/0.12.5/'
    $asset='uv-x86_64-pc-windows-msvc.zip'
    $checksum=(Invoke-WebRequest -UseBasicParsing -TimeoutSec 60 -Uri ($base+$asset+'.sha256')).Content
    if($checksum -is [byte[]]){$checksum=[Text.Encoding]::UTF8.GetString($checksum)}
    if($checksum -notmatch '\b([a-fA-F0-9]{64})\b'){throw 'Invalid official uv checksum'}
    $expected=$Matches[1]
    $archive=Join-Path $directory $asset
    $cachedArchiveValid=(Test-Path -LiteralPath $archive) -and ((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash -eq $expected)
    if(-not $cachedArchiveValid){Invoke-WebRequest -UseBasicParsing -TimeoutSec 60 -Uri ($base+$asset) -OutFile $archive}
    if((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash -ne $expected){throw 'uv checksum mismatch'}
    Expand-Archive -LiteralPath $archive -DestinationPath $directory -Force
}
& $uv sync --project $projectRoot --python 3.11 --managed-python --locked --no-editable --link-mode copy
if($LASTEXITCODE -ne 0){throw 'Dependency installation failed'}
if($Action -eq 'verify'){
    $arguments=@((Join-Path $PSScriptRoot 'verify_install.py'))
}else{
    $arguments=@((Join-Path $PSScriptRoot 'entry.py'),$Action)
}
if($Action -eq 'generate'){$arguments+=@($Spec,'--job',$Job)}
if($Action -eq 'research'){$arguments+=@($ResearchAction)}
if($Once -and $Action -eq 'status'){$arguments+='--once'}
& $python -X utf8 @arguments
exit $LASTEXITCODE
