# pool



VSP1 SPD ADJ is line 3

POOL 1800
SPA    2750
HIGH SPEED  3450
CLEANER 2200
POOL HEAT
SPA HEAT


ssh -o ServerAliveInterval=15 -o ServerAliveCountMax=3 arduino@192.168.5.129
sudo nmcli connection modify id mapleleaf1 802-11-wireless.powersave 2

git add .
git commit -m "Working web and cloud updates. sketch handle_packet in test mode though"
git push -u origin HEAD

 sudo  journalctl --vacuum-time=1s

 arduino-app-cli monitor

 arduino-app-cli app logs user:poolController --follow

arduino-app-cli app start poolController
