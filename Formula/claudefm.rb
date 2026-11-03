class Claudefm < Formula
  desc "Lo-fi radio with animated Clawd scenes in your terminal"
  homepage "https://github.com/jurek-zsl/claudefm"
  url "https://github.com/jurek-zsl/claudefm/archive/refs/tags/v1.2.0.tar.gz"
  sha256 "08fbdfa80c14d9829eca9533a0f7242bcea930fcb48766ff9c0ce90a371097ab"
  license "MIT"

  depends_on :macos
  depends_on "mpv"
  depends_on "python@3.14"
  depends_on "yt-dlp"

  def install
    libexec.install "claudefm"
    (libexec/"bin").install "bin/claudefm"
    inreplace libexec/"bin/claudefm",
              "#!/usr/bin/env python3",
              "#!#{formula_opt_bin("python@3.14")}/python3.14"
    bin.install_symlink libexec/"bin/claudefm"
    pkgshare.install "LICENSE", "NOTICE"
  end

  test do
    assert_equal "claudefm #{version}\n", shell_output("#{bin}/claudefm --version")
    assert_match "--no-audio", shell_output("#{bin}/claudefm --help")

    (testpath/"smoke.py").write <<~PYTHON
      import sys
      sys.path.insert(0, "#{libexec}")
      from claudefm.audio import AudioPlayer
      from claudefm.sprites import sample_activity
      from claudefm.tui import TUI, visible_width

      player = AudioPlayer(enabled=False)
      try:
          tui = TUI(player, initial_theme="light", initial_activity="bike")
          lines = tui.render_lines(80, 24)
          assert len(lines) == 24
          assert all(visible_width(line) == 80 for line in lines)
          assert "VISUALS" in lines[0]
          assert len(sample_activity("bike", 1)) == 26
          tui.advance(300)
          assert tui.activity_key == "walk"
          assert tui.activity_elapsed == 0
      finally:
          player.stop()
    PYTHON
    system formula_opt_bin("python@3.14")/"python3.14", testpath/"smoke.py"
  end
end
