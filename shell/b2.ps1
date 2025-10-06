param (
    [Parameter(Mandatory = $true)]
    [string]$Date
)

$ErrorActionPreference = 'Stop'

$appUserFile = "applications_users_$Date.csv"
$deviceUserFile = "devices_users_$Date.csv"
$appDeviceComboFile = "app_device_combinations_$Date.csv"

$appUsers = @{}
$deviceUsers = @{}
$userApps = @{}
$userDevices = @{}

Write-Host "Processing files for $Date..."

Get-ChildItem -Filter "user.application.$Date-*.csv" | ForEach-Object {
    Write-Host "Reading $_.Name"
    Import-Csv $_.FullName -Header "user","application" | ForEach-Object {
        $user = $_.user
        $app = $_.application

        if (![string]::IsNullOrWhiteSpace($user) -and ![string]::IsNullOrWhiteSpace($app)) {
            if (-not $appUsers.ContainsKey($app)) {
                $appUsers[$app] = [System.Collections.Generic.HashSet[string]]::new()
            }
            $appUsers[$app].Add($user)

            if (-not $userApps.ContainsKey($user)) {
                $userApps[$user] = [System.Collections.Generic.HashSet[string]]::new()
            }
            $userApps[$user].Add($app)
        }
    }
}

Get-ChildItem -Filter "user.device.$Date-*.csv" | ForEach-Object {
    Write-Host "Reading $_.Name"
    Import-Csv $_.FullName -Header "user","device" | ForEach-Object {
        $user = $_.user
        $device = $_.device

        if (![string]::IsNullOrWhiteSpace($user) -and ![string]::IsNullOrWhiteSpace($device)) {
            if (-not $deviceUsers.ContainsKey($device)) {
                $deviceUsers[$device] = [System.Collections.Generic.HashSet[string]]::new()
            }
            $deviceUsers[$device].Add($user)

            if (-not $userDevices.ContainsKey($user)) {
                $userDevices[$user] = [System.Collections.Generic.HashSet[string]]::new()
            }
            $userDevices[$user].Add($device)
        }
    }
}

Write-Host "Writing $appUserFile"
$appUsers.GetEnumerator() | Sort-Object Name | ForEach-Object {
    [PSCustomObject]@{
        application = $_.Key
        'number of unique users' = $_.Value.Count
    }
} | Export-Csv $appUserFile -NoTypeInformation

Write-Host "Writing $deviceUserFile"
$deviceUsers.GetEnumerator() | Sort-Object Name | ForEach-Object {
    [PSCustomObject]@{
        device = $_.Key
        'number of unique users' = $_.Value.Count
    }
} | Export-Csv $deviceUserFile -NoTypeInformation

Write-Host "Writing $appDeviceComboFile"
$comboSet = [System.Collections.Generic.HashSet[string]]::new()

$userApps.Keys | ForEach-Object {
    $user = $_
    if ($userDevices.ContainsKey($user)) {
        foreach ($app in $userApps[$user]) {
            foreach ($device in $userDevices[$user]) {
                $comboSet.Add("$app,$device")
            }
        }
    }
}

$comboSet | Sort-Object | ForEach-Object {
    $parts = $_ -split ","
    [PSCustomObject]@{
        application = $parts[0]
        device      = $parts[1]
    }
} | Export-Csv $appDeviceComboFile -NoTypeInformation

Write-Host "Completed processing for $Date"
