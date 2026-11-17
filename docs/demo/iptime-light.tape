Output docs/products/dotfiles/iptime-cli/docs/demo/iptime-light.gif
Set Shell bash
Set FontSize 18
Set Width 1200
Set Height 700
Set Padding 28
Set Theme "Catppuccin Latte"
Set TypingSpeed 45ms
Set WindowBar Colorful
Set BorderRadius 10
Hide
Set TypingSpeed 0
Sleep 500ms
Type "export PS1='$ '"
Enter
Type "cd docs/products/dotfiles/iptime-cli"
Enter
Type "export PYTHONPATH=src XDG_CONFIG_HOME=/tmp/iptime-demo IPTIME_HOST=127.0.0.1:18180 IPTIME_PASSWORD=secret"
Enter
Type "python3 -m iptime_cli.fake_router --port 18180 >/tmp/iptime-demo-router.log 2>&1 & FAKE_ROUTER_PID=$!"
Enter
Type `iptime() { python3 -m iptime_cli "$@"; }`
Enter
Sleep 1s
Type "clear"
Enter
Sleep 600ms
Show
Set TypingSpeed 45ms
Type "iptime clients"
Sleep 350ms
Enter
Sleep 2s
Type "iptime port add 'Game server' --target 192.168.0.10 --ext 25565 --dry-run"
Sleep 350ms
Enter
Sleep 3s
Hide
Type "kill $FAKE_ROUTER_PID"
Enter
Sleep 300ms
