$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir
$NodeExe = Join-Path $ProjectDir "tools\node-v22.11.0-win-x64\node.exe"
$LarkCli = Join-Path $ProjectDir "tools\lark-mcp-runtime\node_modules\@larksuiteoapi\lark-mcp\dist\cli.js"

$AppId = $env:FEISHU_APP_ID
if ([string]::IsNullOrWhiteSpace($AppId)) {
    $AppId = $env:APP_ID
}

$AppSecret = $env:FEISHU_APP_SECRET
if ([string]::IsNullOrWhiteSpace($AppSecret)) {
    $AppSecret = $env:APP_SECRET
}

if ([string]::IsNullOrWhiteSpace($AppId) -or [string]::IsNullOrWhiteSpace($AppSecret)) {
    Write-Error "Missing Feishu credentials. Set FEISHU_APP_ID and FEISHU_APP_SECRET before starting Codex."
    exit 1
}

$Tools = $env:FEISHU_MCP_TOOLS
if ([string]::IsNullOrWhiteSpace($Tools)) {
    $Tools = "docx.v1.document.create,docx.v1.document.convert,docx.v1.documentBlockChildren.create,docx.v1.documentBlock.patch,docx.v1.documentBlock.list,docx.v1.document.get,docx.v1.document.rawContent,drive.v1.file.createFolder,drive.v1.file.copy,drive.v1.exportTask.create,drive.v1.exportTask.get"
}

$Scope = $env:FEISHU_MCP_SCOPE
if ([string]::IsNullOrWhiteSpace($Scope)) {
    $Scope = "offline_access docx:document"
}

$env:Path = "$(Split-Path -Parent $NodeExe);$env:Path"

$Args = @(
    $LarkCli,
    "mcp",
    "-a", $AppId,
    "-s", $AppSecret,
    "--oauth",
    "--token-mode", "auto",
    "-l", "zh",
    "-t", $Tools
)

if (-not [string]::IsNullOrWhiteSpace($Scope)) {
    $Args += @("--scope", $Scope)
}

& $NodeExe @Args
exit $LASTEXITCODE
