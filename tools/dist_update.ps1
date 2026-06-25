# Auto-atualizador da versão .exe: baixa a release mais recente do GitHub e
# substitui os arquivos desta pasta. Não exige Python nem Git.
$ErrorActionPreference = 'Stop'
$repo = '99833471/rpa-download'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host 'Buscando a versao mais recente no GitHub...'
$headers = @{ 'User-Agent' = 'rpa-updater' }
$rel = Invoke-RestMethod -Uri "https://api.github.com/repos/$repo/releases/latest" -Headers $headers
$asset = $rel.assets | Where-Object { $_.name -like '*.zip' } | Select-Object -First 1
if (-not $asset) { throw 'Nenhum arquivo .zip encontrado na release mais recente.' }

$sizeMB = [math]::Round($asset.size / 1MB, 1)
Write-Host "Baixando $($asset.name) ($sizeMB MB) - versao $($rel.tag_name)..."
$zip = Join-Path $env:TEMP 'rpa_update.zip'
Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $zip -Headers $headers

$tmp = Join-Path $env:TEMP 'rpa_update_extract'
if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }
Expand-Archive -Path $zip -DestinationPath $tmp -Force

$inner = Get-ChildItem $tmp -Directory | Select-Object -First 1
if (-not $inner) { $inner = Get-Item $tmp }

Write-Host 'Atualizando arquivos...'
Copy-Item -Path (Join-Path $inner.FullName '*') -Destination $here -Recurse -Force

Remove-Item $zip -Force -ErrorAction SilentlyContinue
Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
Write-Host ''
Write-Host "Pronto! Voce esta na versao mais recente ($($rel.tag_name))."
