Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$b = [System.Windows.Forms.SystemInformation]::VirtualScreen
$bmp = New-Object System.Drawing.Bitmap $b.Width, $b.Height
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($b.X, $b.Y, 0, 0, $bmp.Size)
$path = 'C:\Users\kirill\Desktop\code\private-browser\05-real-pywebview.png'
$bmp.Save($path)
$g.Dispose()
$bmp.Dispose()
Write-Host "saved $path size=$($b.Width)x$($b.Height)"
