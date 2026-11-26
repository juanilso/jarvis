# Chrome do Jarvis: abre um Chrome SEPARADO (perfil próprio) que o Jarvis consegue controlar pela sua rede Tailscale.
# - Não usa o seu perfil do dia a dia: o Jarvis só enxerga os sites em que você entrar NESTA janela.
# - A porta fica liberada só para a sua rede Tailscale (nunca para a internet) e só enquanto esta janela estiver aberta.
# - Fechou o Chrome do Jarvis = acesso encerrado.
$ErrorActionPreference = "Stop"
$Porta = 9222
$Perfil = Join-Path $env:LOCALAPPDATA "JarvisChrome"
$Inicio = "https://www.google.com/?hl=pt-BR"

function Achar($lista) { foreach ($c in $lista) { if ($c -and (Test-Path $c)) { return $c } } return $null }
$Chrome = Achar @("$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
                  "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
                  "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe")
$TS = (Get-Command tailscale.exe -ErrorAction SilentlyContinue).Source
if (-not $TS) { $TS = Achar @("$env:ProgramFiles\Tailscale\tailscale.exe", "${env:ProgramFiles(x86)}\Tailscale\tailscale.exe") }
if (-not $Chrome) { Write-Host "Nao achei o Google Chrome instalado." -ForegroundColor Red; Read-Host "Enter para sair"; exit 1 }
if (-not $TS) { Write-Host "Nao achei o Tailscale. Instale e entre na sua conta." -ForegroundColor Red; Read-Host "Enter para sair"; exit 1 }

$IP = (& $TS ip -4 2>$null | Select-Object -First 1)
if (-not $IP) { Write-Host "O Tailscale nao esta conectado. Abra o Tailscale e entre." -ForegroundColor Red; Read-Host "Enter para sair"; exit 1 }

function Rodando { Get-CimInstance Win32_Process -Filter "Name='chrome.exe'" | Where-Object { $_.CommandLine -like "*JarvisChrome*" } }

# libera a porta SO na rede Tailscale (o Chrome em si escuta apenas no proprio PC)
& $TS serve --bg --tcp $Porta "tcp://127.0.0.1:$Porta" | Out-Null

if (-not (Rodando)) {
  Start-Process $Chrome -ArgumentList @("--remote-debugging-port=$Porta", "--user-data-dir=`"$Perfil`"",
    "--no-first-run", "--no-default-browser-check", "--window-name=Chrome do Jarvis", $Inicio) | Out-Null
}
$Cmd = "/navegador $IP"
try { Set-Clipboard -Value $Cmd } catch {}

Write-Host ""
Write-Host "  ==============================================================" -ForegroundColor Cyan
Write-Host "   CHROME DO JARVIS ABERTO" -ForegroundColor Cyan
Write-Host "  ==============================================================" -ForegroundColor Cyan
Write-Host "   Na primeira vez, mande isto ao Jarvis (ja esta copiado):"
Write-Host "      $Cmd" -ForegroundColor Yellow
Write-Host ""
Write-Host "   - Entre NESTA janela so nos sites que o Jarvis precisa usar."
Write-Host "   - Ele nunca digita senhas nem paga nada: nessas telas, voce preenche."
Write-Host "   - Para encerrar o acesso: feche o Chrome do Jarvis (ou esta janela)."
Write-Host "  ==============================================================" -ForegroundColor Cyan

try {
  Start-Sleep -Seconds 3
  while (Rodando) { Start-Sleep -Seconds 3 }
} finally {
  & $TS serve --tcp=$Porta off 2>$null | Out-Null
  Write-Host "Acesso encerrado (porta fechada no Tailscale)." -ForegroundColor Green
  Start-Sleep -Seconds 2
}
