param([string]$Out='trace', [string]$Cue='game.cue', [string]$FrameAddr='', [string]$Count='2401:2520', [string]$Trace='2401:2520:8', [int]$Seconds=3600, [int]$Tail=0)
# hwmodel: run the interpreter-mode hwtrace Flycast build (flycast.exe here is NOT the template build).
# Writes per-PC execution counts for frames $Count and full traces for frames $Trace (A:B:STEP)
# into .\$Out\, then Flycast exits by itself (HWTRACE_EXIT). $FrameAddr = physical address of a
# guest word stored once per frame with the frame number (re4dc_pcs LAST_FRAME = syms.txt 4th
# offset + 0x0c000000 + 64); derived from syms.txt if empty. Without syms.txt (non-D367 builds,
# e.g. the D349 room target) Flycast is launched directly and -FrameAddr is required.
# -Tail N (syms.txt builds): Flycast does not exit by itself; the log reader (read_log.py,
# RE4DC_LOG_STOP) stops N frames after the window's last frame, after a final drain, so the log
# records of the window's last tick are kept (counts and traces are unchanged: the window is the same).
Set-Location $PSScriptRoot
New-Item -ItemType Directory -Force $Out | Out-Null
$haveSyms = Test-Path 'syms.txt'
if ($FrameAddr -eq '') {
  if (-not $haveSyms) { throw 'no syms.txt: pass -FrameAddr' }
  $syms = (Get-Content 'syms.txt' -Raw).Trim() -split '\s+'
  $FrameAddr = '{0:x8}' -f ([Convert]::ToInt64($syms[3].Replace('0x',''), 16) + 0x0c000000 + 64)
}
$env:HWTRACE_DIR = (Resolve-Path $Out).Path
$env:HWTRACE_FRAMEADDR = $FrameAddr
$env:HWTRACE_COUNT = $Count
$env:HWTRACE_TRACE = $Trace
$env:HWTRACE_EXIT = '1'
if ($Tail -gt 0 -and $haveSyms) {
  $last = [Math]::Max([int]($Count.Split(':')[1]), [int]($Trace.Split(':')[1]))
  $env:HWTRACE_EXIT = '0'
  $env:RE4DC_LOG_STOP = ('0x{0:x}:{1}' -f ([Convert]::ToInt64($FrameAddr, 16) - 0x0c000000), ($last + $Tail))
}
"frameaddr $FrameAddr count $Count trace $Trace cue $Cue tail $Tail" | Out-File "$Out\params.txt" -Encoding ascii
$t0 = Get-Date
if ($haveSyms) {
  powershell -NoProfile -ExecutionPolicy Bypass -File boot2.ps1 -Cue $Cue -Seconds $Seconds *> "$Out\run-output.txt"
} else {
  while (@(Get-Process flycast -ErrorAction SilentlyContinue).Count -ge 8) { Start-Sleep -Seconds 5 }
  (Get-Content emu.cfg) -replace '^Debug.GDBEnabled = yes', 'Debug.GDBEnabled = no' | Set-Content emu.cfg -Encoding ascii
  $p = Start-Process -FilePath '.\flycast.exe' -ArgumentList "`"$Cue`"" -PassThru -WindowStyle Hidden -RedirectStandardOutput 'serial.txt' -RedirectStandardError 'serial.err.txt'
  Set-Content -Path 'flycast.pid' -Value $p.Id -Encoding ascii -NoNewline
  if (-not $p.WaitForExit($Seconds * 1000)) { Stop-Process -Id $p.Id -Force; "timeout after $Seconds s" | Out-File "$Out\run-output.txt" -Encoding ascii }
}
"elapsed_s $(((Get-Date) - $t0).TotalSeconds)" | Out-File "$Out\elapsed.txt" -Encoding ascii
