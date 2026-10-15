<#
prune_build_outputs.ps1 -- Windows twin of prune_build_outputs.py (disk hygiene rule, user 2026-10-15).
Prunes staged disc images older than -IdleHours (6) in the Flycast evidence roots. prune_build_outputs.sh runs it
(through WSL interop) unless --no-windows; it can also run alone from Windows:
  powershell -NoProfile -ExecutionPolicy Bypass -File prune_build_outputs.ps1 [-Apply] [-List]
Deletes only: *.iso *.cdi *.chd track*.raw track*.bin, and *.bin / *.img > 50 MB, in evidence dirs (top-level dirs of
a root) whose newest file or dir is older than the idle window. Keeps: anything under a data\ or hwmodel-bin dir,
flycast.exe (never matched), images > 1.2 GB or with the GameCube disc magic, protected folder names (release, candidate,
benchmark, SD, superseded discs, re4-assets-private, active lanes), the release tokens, and every path or distinctive dir
name found in the reference corpus the WSL side writes (refs-latest.txt / tokens-latest.txt; the BASE disc trap).
-Apply deletes and writes <ManifestDir>\<timestamp>-win.tsv (path, bytes, mtime, nlink, reason).
#>
param(
  [switch]$Apply,
  [switch]$List,
  [double]$IdleHours = 6,
  [string[]]$Roots = @('C:\Flycast-Evidence\re4-dreamcast', 'D:\Flycast-Evidence\re4-dreamcast'),
  [string]$ManifestDir = '\\wsl.localhost\Ubuntu-24.04\root\probe\_prune-manifests',
  [string]$Stamp = (Get-Date -Format 'yyyyMMdd-HHmmss')
)
$ErrorActionPreference = 'Continue'
$cut = (Get-Date).AddHours(-$IdleHours)
$protect = @('sh4zam*', 't2exact*', 'farhalf*', 'worldlod*', 'skiptick*', 'ps2cast*', 't13rc', 't14rc', 'fullplay',
  'hwmodel-bin', 're4-assets-private', 'RE4DC-Test13-*', 'RE4DC-Test14-Candidate*', 'RE4DC-Benchmark-Part1*',
  'RE4DC-Benchmark-Part2*', 'RE4DC-Benchmark-ZAMR*', 'RE4DC-Benchmark-WLODP*', 'RE4DC-Bench-LinkOrder2*',
  'RE4DC-Bench-LinkOrder-D*', 'LO Control*', 'RE4DC-SD-Backups*', 'RE4DC-superseded-discs*', '_disccache', '_bench-discs')
$tokensKeep = @('05e5ff76', 'bb2c4c51', 'aa0f40a1', '63df6c0f')
$generic = @('obj', 'objs', 'build', 'builds', 'out', 'disc', 'discs', 'tree', 'base', 'work', 'stage', 'tmp', 'data',
  'bench', 'gdemu', 'logs', 'fix', 'hold', 'route', 'lanes')
function ToWsl([string]$p) { '/mnt/' + $p.Substring(0, 1).ToLower() + ($p.Substring(2) -replace '\\', '/') }
$refs = New-Object 'System.Collections.Generic.List[string]'
$ctok = New-Object 'System.Collections.Generic.HashSet[string]'
$rf = Join-Path $ManifestDir 'refs-latest.txt'; $tf = Join-Path $ManifestDir 'tokens-latest.txt'
if (Test-Path -LiteralPath $rf) { foreach ($l in [IO.File]::ReadAllLines($rf)) { if ($l) { $refs.Add($l) } } }
else { Write-Output "prune(win): WARNING no $rf (run prune_build_outputs.sh once); keeping every referenced-name check empty" }
if (Test-Path -LiteralPath $tf) { foreach ($l in [IO.File]::ReadAllLines($tf)) { [void]$ctok.Add($l) } }
$keepFile = Join-Path $ManifestDir 'keep.txt'
$keepLines = @()
if (Test-Path -LiteralPath $keepFile) { $keepLines = Get-Content -LiteralPath $keepFile | Where-Object { $_ -and -not $_.StartsWith('#') } }
function Referenced([string]$w) {
  foreach ($r in $refs) { if ($r -eq $w -or $r.StartsWith($w + '/')) { return $true } }
  return $false
}
function Distinctive([string]$n) {
  ($n.Length -ge 5 -and -not ($generic -contains $n.ToLower()) -and $n -match '\d') -or
  ($n.Length -ge 8 -and -not ($generic -contains $n.ToLower()) -and $n.Contains('-'))
}
function IsGc([string]$p) {
  try { $fs = [IO.File]::OpenRead($p); $b = New-Object byte[] 32; [void]$fs.Read($b, 0, 32); $fs.Close()
    return ($b[28] -eq 0xC2 -and $b[29] -eq 0x33 -and $b[30] -eq 0x9F -and $b[31] -eq 0x3D) } catch { return $true }
}
$todo = @(); $kept = @{}; $perRoot = @{}
foreach ($root in $Roots) {
  if (-not (Test-Path -LiteralPath $root)) { continue }
  $t0 = Get-Date
  foreach ($top in [IO.Directory]::EnumerateDirectories($root)) {
    $name = [IO.Path]::GetFileName($top)
    $why = $null
    foreach ($pat in $protect) { if ($name -like $pat) { $why = "protected name $name"; break } }
    if (-not $why) { foreach ($k in $tokensKeep + ($keepLines | Where-Object { $_ -notmatch '[\\/]' })) { if ($name.Contains($k)) { $why = "token $k"; break } } }
    if (-not $why) { foreach ($k in ($keepLines | Where-Object { $_ -match '[\\/]' })) { if ((ToWsl $top).StartsWith($k.TrimEnd('/')) -or $top.StartsWith($k)) { $why = "keep.txt $k"; break } } }
    $w = ToWsl $top
    if (-not $why -and ((Referenced $w) -or ((Distinctive $name) -and $ctok.Contains($name)))) { $why = "referenced by harness/docs ($name)" }
    $di = New-Object IO.DirectoryInfo $top
    $items = @($di.EnumerateFileSystemInfos('*', [IO.SearchOption]::AllDirectories))
    # newest mtime per directory below $top (an evidence dir often holds many runs: the idle test is per run dir,
    # i.e. the directory that holds the disc image, recursively)
    $dn = @{}; $dn[$top] = $di.LastWriteTime
    foreach ($i in $items) {
      $p = if ($i -is [IO.DirectoryInfo]) { $i.FullName } else { [IO.Path]::GetDirectoryName($i.FullName) }
      while ($p -and $p.Length -ge $top.Length) {
        if (-not $dn.ContainsKey($p) -or $dn[$p] -lt $i.LastWriteTime) { $dn[$p] = $i.LastWriteTime }
        $p = [IO.Path]::GetDirectoryName($p)
      }
    }
    $newest = $dn[$top]
    $files = @()
    foreach ($i in $items) {
      if ($i -isnot [IO.FileInfo]) { continue }
      $n = $i.Name.ToLower(); $ext = $i.Extension.ToLower()
      $isDisc = ($ext -in '.iso', '.cdi', '.chd') -or ($n -match '^track\d+\.(raw|bin|iso)$') -or (($ext -in '.bin', '.img') -and $i.Length -gt 50MB)
      if (-not $isDisc) { continue }
      $rel = $i.FullName.Substring($top.Length + 1)
      $parts = $rel.Split('\')
      if ($parts.Count -gt 1 -and (($parts[0..($parts.Count - 2)] | Where-Object { $_ -ieq 'data' -or $_ -ieq 'hwmodel-bin' }).Count -gt 0)) { continue }
      if ($i.Length -gt 1.2GB -or (IsGc $i.FullName)) { $kept[$i.FullName] = @($i.Length, 'possible source disc'); continue }
      if ($why) { if (-not $kept.ContainsKey($top)) { $kept[$top] = @(0, $why) }; $kept[$top][0] += $i.Length; continue }
      if ($i.LastWriteTime -gt $cut -or (Referenced (ToWsl $i.FullName))) { continue }
      $pd = $i.DirectoryName
      if ($dn[$top] -gt $cut -and (($parts | Where-Object { $_ -like '_disc*' -or $_ -like 'base*' -or $_ -like 'disc*' }).Count -gt 0)) {
        # a disc store (_discs\..., base\...) of an evidence dir that is still in use: a lane may run from it again
        $k = "$pd"; if (-not $kept.ContainsKey($k)) { $kept[$k] = @(0, 'disc store of an active evidence dir') }; $kept[$k][0] += $i.Length; continue }
      if ($dn[$pd] -gt $cut) { $k = "$pd"; if (-not $kept.ContainsKey($k)) { $kept[$k] = @(0, 'run dir active') }; $kept[$k][0] += $i.Length; continue }
      $pn = [IO.Path]::GetFileName($pd)
      if ($pd -ne $top -and ((Referenced (ToWsl $pd)) -or ((Distinctive $pn) -and $ctok.Contains($pn)))) {
        if (-not $kept.ContainsKey($pd)) { $kept[$pd] = @(0, "referenced by harness/docs ($pn)") }; $kept[$pd][0] += $i.Length; continue }
      $files += $i
    }
    if ($files.Count) { $todo += , @($root, $top, $files, $newest) }
  }
  if (-not $List) { } else { Write-Output ('scanned {0} in {1:N0} s' -f $root, ((Get-Date) - $t0).TotalSeconds) }
}
$total = 0; $shared = 0
if ($Apply -and $todo.Count) {
  $mf = Join-Path $ManifestDir "$Stamp-win.tsv"
  $sw = New-Object IO.StreamWriter($mf, $false)
  $sw.WriteLine("path`tbytes`tmtime`tnlink`treason")
}
foreach ($u in $todo) {
  $root, $top, $files, $newest = $u
  $b = 0; $s = 0
  foreach ($f in $files) { if ($f.LinkType -eq 'HardLink') { $s += $f.Length } else { $b += $f.Length } }
  if ($List) { Write-Output ('  {0,8:N2} GB (+{1:N2} GB linked) {2}' -f ($b / 1GB), ($s / 1GB), $top) }
  if ($Apply) {
    # re-check: no new activity in the evidence dir since the scan
    $busyDirs = @{}
    foreach ($rd in ($files | ForEach-Object { $_.DirectoryName } | Sort-Object -Unique)) {
      $di = New-Object IO.DirectoryInfo $rd
      $busy = $di.LastWriteTime -gt $cut
      if (-not $busy) { foreach ($d in $di.EnumerateDirectories('*', [IO.SearchOption]::AllDirectories)) { if ($d.LastWriteTime -gt $cut) { $busy = $true; break } } }
      if ($busy) { $busyDirs[$rd] = 1; Write-Output "  skip (became active): $rd" }
    }
    $files = @($files | Where-Object { -not $busyDirs.ContainsKey($_.DirectoryName) })
    $b = 0; $s = 0
    foreach ($f in $files) {
      $f.Refresh()
      if (-not $f.Exists -or $f.LastWriteTime -gt $cut) { continue }
      $hl = $f.LinkType -eq 'HardLink'
      try { [IO.File]::Delete($f.FullName) } catch { Write-Output "  could not delete $($f.FullName): $_"; continue }
      if ($hl) { $s += $f.Length } else { $b += $f.Length }
      $sw.WriteLine(("{0}`t{1}`t{2}`t{3}`tdisc" -f $f.FullName, $f.Length, $f.LastWriteTime.ToString('s'), $(if ($hl) { '2+' } else { '1' })))
    }
  }
  $total += $b; $shared += $s
  if (-not $perRoot.ContainsKey($root)) { $perRoot[$root] = @(0, 0, 0) }
  $perRoot[$root][0] += $b; $perRoot[$root][1] += $s; $perRoot[$root][2] += $files.Count
}
if ($Apply -and $todo.Count) { $sw.Close(); Write-Output "manifest: $mf" }
Write-Output 'kept (largest protected evidence dirs with disc images):'
$kept.GetEnumerator() | Sort-Object { - $_.Value[0] } | Select-Object -First 15 | ForEach-Object {
  if ($_.Value[0] -gt 200MB) { Write-Output ('  {0,8:N2} GB {1} -- {2}' -f ($_.Value[0] / 1GB), $_.Key, $_.Value[1]) } }
Write-Output ('{0} per evidence root (sole-link bytes; +hard-linked bytes freed only when every link goes):' -f $(if ($Apply) { 'FREED' } else { 'WOULD FREE' }))
foreach ($k in $perRoot.Keys) { Write-Output ('  {0,8:N2} GB  (+{1:N2} GB linked) {2,6} files  {3}' -f ($perRoot[$k][0] / 1GB), ($perRoot[$k][1] / 1GB), $perRoot[$k][2], $k) }
Write-Output ('TOTAL(win) {0} {1:N2} GB (+{2:N2} GB hard-linked); evidence dirs {3}' -f $(if ($Apply) { 'freed' } else { 'would free' }), ($total / 1GB), ($shared / 1GB), $todo.Count)
