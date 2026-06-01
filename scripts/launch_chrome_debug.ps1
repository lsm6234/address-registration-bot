param(
    [int]$Port = 9222,
    [string]$Address = "127.0.0.1",
    [string]$ProfileDir = "$env:LOCALAPPDATA\AddressRegBot\chrome-profile",
    [switch]$KeepRelay
)

$ErrorActionPreference = "Stop"

if ($Port -lt 1024 -or $Port -gt 65535) {
    throw "Port must be between 1024 and 65535."
}

function Test-LoopbackAddress([string]$Value) {
    if ([string]::IsNullOrWhiteSpace($Value)) {
        return $false
    }
    return $Value.Trim() -in @("127.0.0.1", "localhost", "::1")
}

function Test-AllowedDebugAddress([string]$Value) {
    if ([string]::IsNullOrWhiteSpace($Value)) {
        return $false
    }
    $trimmed = $Value.Trim()
    if (Test-LoopbackAddress $trimmed) {
        return $true
    }
    $ip = $null
    if (-not [System.Net.IPAddress]::TryParse($trimmed, [ref]$ip)) {
        return $false
    }
    $bytes = $ip.GetAddressBytes()
    if ($bytes.Length -ne 4) {
        return $false
    }
    # Allow private/local interface addresses only. This supports WSL host IPs
    # such as 10.x.x.x while refusing public remote debugging exposure.
    if ($bytes[0] -eq 10) { return $true }
    if ($bytes[0] -eq 172 -and $bytes[1] -ge 16 -and $bytes[1] -le 31) { return $true }
    if ($bytes[0] -eq 192 -and $bytes[1] -eq 168) { return $true }
    if ($bytes[0] -eq 169 -and $bytes[1] -eq 254) { return $true }
    return $false
}

function Test-CdpHttp([string]$HostName, [int]$HostPort) {
    try {
        $null = Invoke-WebRequest -UseBasicParsing -Uri "http://$HostName`:$HostPort/json/version" -TimeoutSec 1
        return $true
    } catch {
        return $false
    }
}

function Wait-CdpHttp([string]$HostName, [int]$HostPort) {
    for ($i = 0; $i -lt 30; $i++) {
        if (Test-CdpHttp $HostName $HostPort) {
            return $true
        }
        Start-Sleep -Milliseconds 300
    }
    return $false
}

function Start-CdpTcpRelay([string]$ListenAddress, [int]$ListenPort, [string]$TargetAddress, [int]$TargetPort) {
    $source = @"
using System;
using System.Net;
using System.Net.Sockets;
using System.Threading.Tasks;

public static class AddressBotTcpRelay
{
    public static void Start(string listenAddress, int listenPort, string targetAddress, int targetPort)
    {
        IPAddress ip = IPAddress.Parse(listenAddress);
        TcpListener listener = new TcpListener(ip, listenPort);
        listener.Start();
        try
        {
            while (true)
            {
                TcpClient client = listener.AcceptTcpClient();
                Task.Run(async delegate
                {
                    TcpClient target = null;
                    try
                    {
                        target = new TcpClient();
                        await target.ConnectAsync(targetAddress, targetPort).ConfigureAwait(false);
                        using (client)
                        using (target)
                        {
                            NetworkStream clientStream = client.GetStream();
                            NetworkStream targetStream = target.GetStream();
                            Task toTarget = clientStream.CopyToAsync(targetStream);
                            Task toClient = targetStream.CopyToAsync(clientStream);
                            await Task.WhenAny(toTarget, toClient).ConfigureAwait(false);
                        }
                    }
                    catch
                    {
                        try { client.Close(); } catch { }
                        if (target != null) { try { target.Close(); } catch { } }
                    }
                });
            }
        }
        finally
        {
            listener.Stop();
        }
    }
}
"@
    if (-not ("AddressBotTcpRelay" -as [type])) {
        Add-Type -TypeDefinition $source -Language CSharp
    }
    Write-Host ""
    Write-Host "WSL CDP relay is running. Keep this window open while calibrating."
    Write-Host "Relay:  http://$ListenAddress`:$ListenPort  ->  http://$TargetAddress`:$TargetPort"
    Write-Host "Run bithumb-2-inspect-calibration.cmd in another window."
    Write-Host "Close this window after calibration is finished."
    [AddressBotTcpRelay]::Start($ListenAddress, $ListenPort, $TargetAddress, $TargetPort)
}


function Get-WslGatewayAddress() {
    $script = "import socket; lines=open('/proc/net/route').read().splitlines()[1:]; print(next(socket.inet_ntoa(bytes.fromhex(x.split()[2])[::-1]) for x in lines if x.split()[1]=='00000000'))"
    try {
        $result = & wsl.exe --cd / -- python3 -c $script 2>$null
        if ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrWhiteSpace($result)) {
            return ($result | Select-Object -First 1).Trim()
        }
    } catch {
        return ""
    }
    return ""
}

$Address = $Address.Trim()
if ($Address -eq "" -or $Address -eq "auto") {
    $Address = Get-WslGatewayAddress
    if ([string]::IsNullOrWhiteSpace($Address)) {
        $Address = "127.0.0.1"
    }
}
if (-not (Test-AllowedDebugAddress $Address)) {
    throw "Address must be localhost or a private/local interface IP. Refusing: $Address"
}

$chromeCandidates = @(
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "$env:ProgramFiles(x86)\Google\Chrome\Application\chrome.exe",
    "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
)

$chrome = $chromeCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $chrome) {
    throw "Chrome executable not found. Install Chrome or update scripts\launch_chrome_debug.ps1."
}

New-Item -ItemType Directory -Force -Path $ProfileDir | Out-Null

$chromeDebugAddress = if (Test-LoopbackAddress $Address) { $Address } else { "127.0.0.1" }

Write-Host "Starting dedicated Chrome profile for Address Registration Bot"
Write-Host "ProfileDir: $ProfileDir"
Write-Host "Chrome CDP: http://$chromeDebugAddress`:$Port"
if (-not (Test-LoopbackAddress $Address)) {
    Write-Host "WSL CDP:    http://$Address`:$Port"
}
Write-Host "Login to Bithumb manually in the opened browser, then run the bot."

Start-Process -FilePath $chrome -ArgumentList @(
    "--remote-debugging-address=$chromeDebugAddress",
    "--remote-debugging-port=$Port",
    "--user-data-dir=$ProfileDir",
    "--no-first-run",
    "--new-window",
    "https://www.bithumb.com/react/inout/address"
)

if (-not (Wait-CdpHttp $chromeDebugAddress $Port)) {
    throw "Chrome started, but CDP did not open at http://$chromeDebugAddress`:$Port"
}

if (-not (Test-LoopbackAddress $Address)) {
    if (Test-CdpHttp $Address $Port) {
        Write-Host "WSL CDP endpoint is already reachable: http://$Address`:$Port"
    } elseif ($KeepRelay) {
        Start-CdpTcpRelay -ListenAddress $Address -ListenPort $Port -TargetAddress $chromeDebugAddress -TargetPort $Port
    } else {
        Write-Warning "Chrome is only reachable on localhost. Re-run with -KeepRelay for WSL access."
    }
}
