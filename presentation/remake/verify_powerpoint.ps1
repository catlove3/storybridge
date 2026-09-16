$ErrorActionPreference = 'Stop'
$root = '\\wsl.localhost\Ubuntu\home\zypca\zhili\presentation\remake'
$deckPath = Join-Path $root 'presentation.pptx'
$order = Get-Content -Raw -Encoding utf8 (Join-Path $root 'deck_order.json') | ConvertFrom-Json
$exportDir = Join-Path $root 'powerpoint_preview'
New-Item -ItemType Directory -Force -Path $exportDir | Out-Null
$powerpoint = New-Object -ComObject PowerPoint.Application
# Open only this generated presentation, read-only, without changing other files.
$presentation = $powerpoint.Presentations.Open($deckPath, -1, 0, -1)
$report = [ordered]@{ applicationVersion=$powerpoint.Version; pptxSha256=(Get-FileHash $deckPath -Algorithm SHA256).Hash.ToLower(); testedAt=(Get-Date -Format o); slides=$presentation.Slides.Count; hiddenSlides=@(); textOverflow=@(); media=@(); nativeExports=@(); playback=@{} }
try {
  foreach ($slide in $presentation.Slides) {
    $n=$slide.SlideIndex
    if ($slide.SlideShowTransition.Hidden -ne 0) { $report.hiddenSlides += $n }
    $png=Join-Path $exportDir ('{0:d2}.png' -f $n)
    $slide.Export($png,'PNG',1920,1080)
    $report.nativeExports += $png
    foreach ($shape in $slide.Shapes) {
      if ($shape.HasTextFrame -and $shape.TextFrame.HasText) {
        $bound=$shape.TextFrame2.TextRange.BoundHeight
        if ($bound -gt ($shape.Height + 3)) { $report.textOverflow += @{slide=$n;text=$shape.TextFrame.TextRange.Text;boundHeight=$bound;shapeHeight=$shape.Height} }
      }
      if ($shape.Type -eq 16) {
        $report.media += @{slide=$n;name=$shape.Name;durationMs=$shape.MediaFormat.Length;mediaType=$shape.MediaType}
      }
    }
  }
  $report | ConvertTo-Json -Depth 8 | Set-Content -Encoding utf8 (Join-Path $root 'powerpoint_validation.json')
  # A windowed slide show permits a real Player check without closing other decks.
  $settings=$presentation.SlideShowSettings
  $settings.ShowType=2
  $settings.StartingSlide=1
  $settings.EndingSlide=[int]$order.thanks_slide
  $settings.RangeType=2
  $window=$settings.Run()
  try {
    $report.visiblePlaybackOrder=@()
    $window.View.GotoSlide(1)
    for ($i=1; $i -le [int]$order.main_slides; $i++) {
      $report.visiblePlaybackOrder += $window.View.Slide.SlideIndex
      if ($i -lt [int]$order.main_slides) { $window.View.Next() }
    }
    $window.View.GotoSlide([int]$order.video_slide)
    Start-Sleep -Milliseconds 1500
    $slide=$window.View.Slide
    $report.currentSlide=$slide.SlideIndex
    $movie=$null
    foreach ($shape in $slide.Shapes) { if ($shape.Type -eq 16) { $movie=$shape;break } }
    if ($null -eq $movie) { throw ('No embedded media shape on slide ' + $order.video_slide) }
    $report.playerTarget=@{slide=$slide.SlideIndex;shapeId=$movie.Id;shapeName=$movie.Name}
    $player=$window.View.Player([int]$movie.Id)
    $player.Play()
    Start-Sleep -Milliseconds 2000
    $report.playback=[ordered]@{positionAfter2s=$player.CurrentPosition;stateAfter2s=$player.State;durationMs=$movie.MediaFormat.Length}
    $player.Stop()
  } finally { $window.View.Exit() }
  $report | ConvertTo-Json -Depth 8 | Set-Content -Encoding utf8 (Join-Path $root 'powerpoint_validation.json')
  Write-Output ($report | ConvertTo-Json -Depth 8)
  # SaveAs PDF omits hidden slides by default. Make them visible only in this
  # read-only in-memory copy so the offline PDF includes every Q&A page.
  # The source PPTX is never saved, and keeps its hidden-slide settings.
  foreach ($slide in $presentation.Slides) { $slide.SlideShowTransition.Hidden=0 }
  $presentation.SaveAs((Join-Path $root 'preview.pdf'),32)
} catch {
  $report.playbackError=$_.Exception.Message
  $report | ConvertTo-Json -Depth 8 | Set-Content -Encoding utf8 (Join-Path $root 'powerpoint_validation.json')
  Write-Output ($report | ConvertTo-Json -Depth 8)
} finally {
  try { $presentation.Close() } catch {}
  # Do not quit the application: the user may have other presentations open.
  [void][Runtime.InteropServices.Marshal]::ReleaseComObject($presentation)
  [void][Runtime.InteropServices.Marshal]::ReleaseComObject($powerpoint)
}
