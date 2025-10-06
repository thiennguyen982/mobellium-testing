param (
    [Parameter(Mandatory=$true)]
    [string]$Date,

    [Parameter(Mandatory=$true)]
    [string]$Application
)

$ErrorActionPreference = 'Stop'

$tmpDir = Join-Path $env:TEMP ("daily_users_" + [guid]::NewGuid().ToString())
New-Item -ItemType Directory -Path $tmpDir | Out-Null

try {
    Write-Host "`Date: $Date"
    Write-Host "Application: $Application`n"

    $csvFiles = Get-ChildItem -Filter "user.application.*.csv" | Sort-Object Name |
        Where-Object {
            if ($_ -match "user\.application\.(\d{4}-\d{2}-\d{2})\.csv") {
                $fileDate = [datetime]::Parse($matches[1])
                return $fileDate -le [datetime]::Parse($Date)
            }
            return $false
        }

    if ($csvFiles.Count -eq 0) {
        Write-Warning "No files found up to date $Date"
        return
    }

    $day = 0
    $intersectSet = [System.Collections.Generic.HashSet[string]]::new()

    foreach ($file in $csvFiles) {
        $day++
        Write-Host "Processing: $($file.Name)"

        $usersForDay = [System.Collections.Generic.HashSet[string]]::new()

        Get-Content $file.FullName | ForEach-Object {
            $parts = $_ -split ","
            if ($parts.Length -eq 2 -and $parts[1] -eq $Application) {
                $usersForDay.Add($parts[0]) | Out-Null
            }
        }

        $usersForDay | Sort-Object | Set-Content -Path "$tmpDir\day$day.users.txt"

        if ($day -eq 1) {
            $intersectSet = $usersForDay
        } else {
            $intersectSet = $intersectSet | Where-Object { $usersForDay.Contains($_) } | ForEach-Object { $_ }
            $intersectSet = [System.Collections.Generic.HashSet[string]]::new($intersectSet)
        }

        if ($intersectSet.Count -eq 0) {
            Write-Host "No users remained after day $day. Exiting early..."
            break
        }
    }

    Write-Host "`Users who used '$Application' every day up to $Date:"
    if ($intersectSet.Count -eq 0) {
        Write-Host "(none)"
    } else {
        $intersectSet | Sort-Object
    }
}
finally {
    Remove-Item -Path $tmpDir -Recurse -Force
}
