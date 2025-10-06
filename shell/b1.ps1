param (
    [Parameter(Mandatory=$true)]
    [string]$Path
)

$OneGB = 1GB

$globalStart = Get-Date

$gitDirs = Get-ChildItem -Path $Path -Recurse -Force -Directory -ErrorAction SilentlyContinue |
    Where-Object { Test-Path "$($_.FullName)\.git" }

foreach ($dir in $gitDirs) {
    $start = Get-Date

    try {
        $size = (Get-ChildItem -Path $dir.FullName -Recurse -Force -ErrorAction SilentlyContinue |
            Measure-Object -Property Length -Sum).Sum

        if ($size -gt $OneGB) {
            $sizeGB = [Math]::Round($size / 1GB, 2)
            Write-Host "Directory: $($dir.FullName)"
            Write-Host "Size: $sizeGB GB"

            $end = Get-Date
            $duration = $end - $start
            Write-Host "Time taken: $($duration.TotalSeconds) seconds"
            Write-Host "-----------------------------"
        }
    } catch {
        Write-Warning "Failed to calculate size for $($dir.FullName): $_"
    }
}

$globalEnd = Get-Date
$totalTime = $globalEnd - $globalStart
Write-Host "Total time: $($totalTime.TotalSeconds) seconds"
