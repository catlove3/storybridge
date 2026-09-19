$ErrorActionPreference = 'Stop'
$root = '\\wsl.localhost\Ubuntu\home\zypca\zhili\presentation\remake\readable_20260917'
$deckPath = '\\wsl.localhost\Ubuntu\home\zypca\zhili\presentation\remake\presentation.pptx'
$exportDir = Join-Path $root 'powerpoint_preview'
New-Item -ItemType Directory -Force -Path $exportDir | Out-Null
$powerpoint = New-Object -ComObject PowerPoint.Application
$presentation = $powerpoint.Presentations.Open($deckPath, -1, 0, -1)
$report = [ordered]@{ applicationVersion=$powerpoint.Version; pptxSha256=(Get-FileHash $deckPath -Algorithm SHA256).Hash.ToLower(); testedAt=(Get-Date -Format o); slides=$presentation.Slides.Count; hiddenSlides=@(); textOverflow=@(); media=@() }
try {
  foreach ($slide in $presentation.Slides) {
    $n=$slide.SlideIndex
    if ($slide.SlideShowTransition.Hidden -ne 0) { $report.hiddenSlides += $n }
    $slide.Export((Join-Path $exportDir ('{0:d2}.png' -f $n)), 'PNG', 1920, 1080)
    foreach ($shape in $slide.Shapes) {
      if ($shape.HasTextFrame -and $shape.TextFrame.HasText) {
        $bound=$shape.TextFrame2.TextRange.BoundHeight
        if ($bound -gt ($shape.Height + 3)) { $report.textOverflow += @{slide=$n;text=$shape.TextFrame.TextRange.Text;boundHeight=$bound;shapeHeight=$shape.Height} }
      }
      if ($shape.Type -eq 16) { $report.media += @{slide=$n;durationMs=$shape.MediaFormat.Length} }
    }
  }
  $settings=$presentation.SlideShowSettings
  $settings.ShowType=2
  $settings.StartingSlide=1
  $settings.EndingSlide=13
  $settings.RangeType=2
  $window=$settings.Run()
  try {
    $report.visiblePlaybackOrder=@()
    $window.View.GotoSlide(1)
    for ($i=1; $i -le 13; $i++) {
      $report.visiblePlaybackOrder += $window.View.Slide.SlideIndex
      if ($i -lt 13) { $window.View.Next() }
    }
    $window.View.GotoSlide(11)
    Start-Sleep -Milliseconds 800
    $movie=$null
    foreach ($shape in $window.View.Slide.Shapes) { if ($shape.Type -eq 16) { $movie=$shape; break } }
    if ($null -eq $movie) { throw 'Missing embedded video on slide 11' }
    $player=$window.View.Player([int]$movie.Id)
    $player.Play()
    Start-Sleep -Milliseconds 2000
    $report.playback=@{positionAfter2s=$player.CurrentPosition;durationMs=$movie.MediaFormat.Length}
    $player.Stop()
  } finally { $window.View.Exit() }
  foreach ($slide in $presentation.Slides) { $slide.SlideShowTransition.Hidden=0 }
  $presentation.SaveAs((Join-Path $root 'preview.pdf'),32)
} catch {
  $report.error=$_.Exception.Message
  throw
} finally {
  $report | ConvertTo-Json -Depth 8 | Set-Content -Encoding utf8 (Join-Path $root 'powerpoint_validation.json')
  try { $presentation.Close() } catch {}
  [void][Runtime.InteropServices.Marshal]::ReleaseComObject($presentation)
  [void][Runtime.InteropServices.Marshal]::ReleaseComObject($powerpoint)
}
Write-Output ($report | ConvertTo-Json -Depth 8)
