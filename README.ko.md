# iptime-cli

[English](https://github.com/elfenomenokim/iptime-cli/blob/main/README.md)

새 관리자 화면(펌웨어 16.x)을 쓰는 ipTIME 공유기를 위한 비공식 명령줄 도구이자 파이썬 라이브러리입니다. 접속 기기 목록, DHCP 고정 할당, 포트포워딩, 와이파이·WAN 상태 확인, 원격 관리 끄기를 터미널이나 스크립트, AI 에이전트에서 할 수 있습니다.

> 비공식 도구입니다. EFM Networks와 아무 관계가 없고, 보증이나 지원도 받지 않습니다. ipTIME은 해당 회사의 상표입니다.

```console
$ iptime clients
IP            MAC                NAME        LINK          LEASE LEFT  RESERVED
192.168.0.10  AA:BB:CC:00:00:01  desktop     lan2 wired    static
192.168.0.11  AA:BB:CC:00:00:02  nas         lan4 wired    22h 13m     yes
192.168.0.20  AA:BB:CC:00:00:03  laptop      5g.1 -48 dBm  1h 46m
192.168.0.21  AA:BB:CC:00:00:04  phone       5g.1 -61 dBm  53m 20s
192.168.0.30  AA:BB:CC:00:00:05  smart-plug  2g.1 -70 dBm  19h 26m
```

(함께 들어 있는 가짜 공유기에서 나온 예시이고, 기기는 모두 지어낸 것입니다.)

ipTIME은 국내 가정용 공유기 중 가장 흔하지만 공개 API가 없습니다. 새 관리자 화면(`/ui/`에서 제공되는 Flutter 앱)은 JSON 엔드포인트 하나, `POST /cgi/service.cgi {"method": ..., "params": ...}`로 공유기와 통신합니다. 이 도구는 그 프로토콜을 그대로 씁니다. 우리가 찾은 기존 공개 작업은 펌웨어 14.x의 옛 화면용 npm 패키지 하나뿐이었습니다.

## 왜 쓰나

- **관리자 화면에서 읽을 수 있는 건 명령 하나로 읽습니다.** 접속 기기, 임대 목록, 고정 할당, 포트포워딩, 와이파이, WAN, 펌웨어(새 버전이 있는지까지).
- **펌웨어 확인과 한 줄 업그레이드.** 공유기 자체의 온라인 업그레이드를 쓰고, 재부팅이 끝날 때까지 기다려 줍니다.
- **기본이 안전합니다.** 읽기는 아무것도 바꾸지 않습니다. 쓰기는 항상 먼저 묻고, `--dry-run`을 지원하며, 물어볼 터미널이 없으면 `--yes` 없이는 실행을 거부합니다. 공유기가 평문으로 돌려주는 와이파이 비밀번호는 `--show-secrets`를 줘야만 보입니다.
- **원시 호출 통로.** `iptime call <method> [params]`로 어떤 메서드든 보낼 수 있고, `iptime methods`는 관리자 번들에서 찾은 약 290개 메서드를 어느 펌웨어에서 확인했는지와 함께 보여 줍니다.
- **표준 라이브러리만 씁니다.** 의존성이 없고 파이썬 3.9 이상이면 됩니다.
- **라이브러리로도 씁니다.** `Router(host, user, password).call(method, params)`와 타입이 있는 헬퍼가 있습니다.
- **써 볼 수 있는 가짜 공유기.** `python -m iptime_cli.fake_router`가 지어낸 데이터를 내주므로, 아래 예시를 실제 공유기 없이 그대로 돌려 볼 수 있습니다.

## 설치

```console
$ pipx install iptime-cli     # 권장: 격리된 환경, PATH에 등록
$ uvx iptime-cli --help       # 설치 없이 실행
$ pip install iptime-cli      # 기존 프로젝트 안에서
```

## 설정

값은 명령줄 옵션, 환경 변수, 설정 파일, 기본값 순서로 정해집니다.

| 항목 | 옵션 | 환경 변수 | 설정 파일 키 | 기본값 |
|---|---|---|---|---|
| 공유기 주소 | `--host` | `IPTIME_HOST` | `host` | `192.168.0.1` |
| 관리자 아이디 | `--user` | `IPTIME_USER` | `user` | `admin` |
| 관리자 비밀번호 | — | `IPTIME_PASSWORD` | `password` | 터미널에서 물어봄 |

설정 파일은 macOS·Linux에서 `~/.config/iptime-cli/config`, Windows에서 `%APPDATA%\iptime-cli\config`입니다(`--config 파일` 또는 `IPTIME_CONFIG`로 바꿀 수 있습니다).

```ini
host = 192.168.0.1
user = admin
password = change-me
```

비밀번호가 들어 있으니 `chmod 600 ~/.config/iptime-cli/config`로 막아 두세요. 다른 사용자가 읽을 수 있는 상태면 stderr로 경고합니다(macOS·Linux. Windows는 사용자 폴더 권한으로 보호됩니다). `IPTIME_ADMIN_URL=`, `IPTIME_ADMIN_USER=`, `IPTIME_ADMIN_PASSWORD=` 줄로 된 파일(또는 `IPTIME_HOST=` 등)도 그대로 읽습니다. `--host`에는 `192.168.0.1`, `192.168.0.1:8080`, 전체 URL을 모두 쓸 수 있습니다.

> **로그인하면 브라우저에 열려 있던 관리자 세션이 끊길 수 있습니다.** 공유기는 동시에 열 수 있는 관리자 세션이 적습니다. 이 도구는 끝날 때 로그아웃합니다.

## 사용법

전역 옵션은 명령 앞에도 뒤에도 쓸 수 있습니다. `--json`을 붙이면 모든 읽기 결과를 스크립트용 JSON으로 받습니다.

### 공유기 없이 써 보기

```console
$ python -m iptime_cli.fake_router --port 8080 &
$ export IPTIME_HOST=127.0.0.1:8080 IPTIME_PASSWORD=secret
```

### info

```console
$ iptime info
Model            ipTIME FAKE-1000
Firmware         16.000  (built 2026.01.01 00:00:00)
Latest firmware  16.010  (update available)
Uptime           1d 2h 3m
LAN              192.168.0.1 / 255.255.255.0
DHCP pool        192.168.0.2 - 192.168.0.254
WAN              dhcp 203.0.113.7  gateway 203.0.113.1  up
WAN link         1000f
```

새 버전이 있으면 `iptime firmware upgrade`로 올릴 수 있습니다(아래 참고).

### clients

공유기가 보는 모든 기기(유선·무선)를 DHCP 임대·고정 할당 정보와 합쳐 보여 줍니다. `--wireless`, `--wired`로 거를 수 있습니다.

```console
$ iptime clients --wireless
IP            MAC                NAME        LINK          LEASE LEFT  RESERVED
192.168.0.20  AA:BB:CC:00:00:03  laptop      5g.1 -48 dBm  1h 46m
192.168.0.21  AA:BB:CC:00:00:04  phone       5g.1 -61 dBm  53m 20s
192.168.0.30  AA:BB:CC:00:00:05  smart-plug  2g.1 -70 dBm  19h 26m
```

### wan, wifi

```console
$ iptime wan
Type           dhcp
Status         up (ok)
IP             203.0.113.7
Mask           255.255.255.0
Gateway        203.0.113.1
DNS            198.51.100.2, 198.51.100.3
MAC            AA:BB:CC:00:10:02
MTU            1500
Link speed     1000f
Connected for  1d 2h 1m
Received       2.9 TB
Sent           300.0 GB

$ iptime wifi
BSS   SSID          BAND           CH  SECURITY     ON   HIDDEN  CLIENTS
2g.1  example-2.4G  2g 11ax/40MHz  6   wpa2psk_aes  yes          1
5g.1  example-5G    5g 11ax/80MHz  36  wpa2psk_aes  yes          2
```

`iptime wifi --show-secrets`를 쓰면 PASSWORD 열이 추가됩니다.

### port

```console
$ iptime port list
NAME        PROTO  EXTERNAL     TARGET        INTERNAL     ON
Web server  tcp    8080         192.168.0.10  80           yes
Game range  udp    27000-27010  192.168.0.20  27000-27010  no

$ iptime port add "Test rule" --target 192.168.0.10 --ext 9000-9005 --proto udp --dry-run
dry run, nothing sent:
POST http://127.0.0.1:8080/cgi/service.cgi
{"method": "portforward/add", "params": {"name": "Test rule", "active": true, "protocol": "udp", "target": "192.168.0.10", "src": {"start": 9000, "end": 9005}, "dst": {"start": 9000, "end": 9005}}}

$ iptime port add "Test rule" --target 192.168.0.10 --ext 9000 --int 90 --yes
ok, rules now:
NAME        PROTO  EXTERNAL     TARGET        INTERNAL     ON
Web server  tcp    8080         192.168.0.10  80           yes
Game range  udp    27000-27010  192.168.0.20  27000-27010  no
Test rule   tcp    9000         192.168.0.10  90           yes

$ iptime port rm "Test rule" --yes
ok, rules now:
NAME        PROTO  EXTERNAL     TARGET        INTERNAL     ON
Web server  tcp    8080         192.168.0.10  80           yes
Game range  udp    27000-27010  192.168.0.20  27000-27010  no
```

`--ext`는 WAN 쪽 포트, `--int`는 대상 기기 쪽 포트입니다(생략하면 `--ext`와 같음). `--proto`는 `tcp`, `udp`, `tcpudp` 중 하나입니다. `iptime port list --upnp`는 프로그램이 UPnP로 만든 규칙을 보여 주며, `port rm`은 직접 만든 규칙만 지웁니다.

### dhcp

```console
$ iptime dhcp list
IP            MAC                NAME        STATE            LEASE LEFT
192.168.0.11  AA:BB:CC:00:00:02  NAS         reserved+leased  22h 13m
192.168.0.20  AA:BB:CC:00:00:03  laptop      leased           1h 46m
192.168.0.21  AA:BB:CC:00:00:04  phone       leased           53m 20s
192.168.0.30  AA:BB:CC:00:00:05  smart-plug  leased           19h 26m

$ iptime dhcp reserve aa-bb-cc-00-00-09 192.168.0.40 --name printer --dry-run
dry run, nothing sent:
POST http://127.0.0.1:8080/cgi/service.cgi
{"method": "dhcpd/reservedaddr/add", "params": {"ntag": "lan", "mac": "AA:BB:CC:00:00:09", "ip": "192.168.0.40", "desc": "printer"}}

$ iptime dhcp unreserve AA:BB:CC:00:00:09 --yes
ok: "done"
```

MAC은 `:`나 `-`로 쓰고 대소문자는 가리지 않습니다.

### remote-admin

인자 없이 쓰면 상태를 보여 주고, `on`·`off`로 바꿉니다.

```console
$ iptime remote-admin
LAN admin     HTTP port 80
Remote HTTP   off, port 8080
Remote HTTPS  off, port 8443

$ iptime remote-admin on --dry-run
warning: this opens the router's admin page to the internet.
dry run, nothing sent:
POST http://127.0.0.1:8080/cgi/service.cgi
{"method": "http/config", "params": {"remotehttp_flag": true, "remotehttp_port": 8080, "commit": true}}
```

`off`는 원격(WAN) HTTP 관리만 끄고, 내부망(LAN)의 관리 화면은 그대로 열려 있습니다. `on`은 `--port`를 주지 않으면 저장된 원격 포트를 씁니다.

### firmware

```console
$ iptime firmware check
Running  16.000  (built 2026.01.01 00:00:00)
Latest   16.010
State    update available

$ iptime firmware upgrade --dry-run
dry run, nothing sent (16.000 -> 16.010):
POST http://127.0.0.1:8080/cgi/service.cgi
{"method": "firmware/upgrade/prepare", "params": {"method": "auto"}}
POST http://127.0.0.1:8080/cgi/service.cgi
{"method": "firmware/upgrade/online"}

$ iptime firmware upgrade --yes
[17:31:34] upgrade requested: 16.000 -> 16.010
[17:31:34] stage: starting
[17:31:35] stage: checking
[17:31:36] stage: downloading
[17:31:38] stage: waiting
[17:31:39] stage: writing
[17:31:42] router is rebooting (unreachable)
[17:31:45] stage: idle
firmware upgraded 16.000 -> 16.010 in 11s
```

`check`는 지금 돌아가는 버전과 공유기가 스스로 알려 주는 최신 버전을 비교합니다. `upgrade`는 제조사의 온라인 업그레이드만 씁니다. 공유기가 이미지를 직접 내려받으므로 내 컴퓨터에서 파일을 올리지 않습니다. 관리자 화면의 "지금 업그레이드" 버튼이 보내는 호출 두 개를 보내고, 진행 상태를 확인하다가, 재부팅 동안 기다린 뒤 다시 로그인해 이전 -> 새 버전을 출력합니다.

- **접속이 끊깁니다.** 공유기가 재부팅하면서 네트워크가 몇 분 끊깁니다(공유기가 알려 주는 쓰기 시간은 약 4분). 직접 손으로, 한적한 시간에 실행하세요. 누가 인터넷을 쓰고 있을 때는 피하세요.
- `upgrade`는 먼저 묻습니다. `--yes`는 질문을 건너뛰고, `--dry-run`은 요청 두 개만 출력하고 보내지 않습니다.
- `--if-available`은 이미 최신이면 아무것도 출력하지 않고 0으로 끝납니다.
- `--wait-timeout 초`(기본 1800)는 새 버전으로 돌아올 때까지 기다리는 시간이고, `--poll 초`(기본 10)는 상태 확인 간격입니다. 시간 안에 돌아오지 않으면 종료 코드 1로 알려 주니, 그때는 공유기를 직접 확인하세요.
- 진행 메시지는 stderr로 나가고, `--json`이면 마지막 결과만 출력합니다.
- 공유기가 업그레이드 실패(`download`, `format`, `version`, `internal`)를 알리면 그 이유와 함께 멈춥니다.

### reboot

`iptime reboot`는 먼저 물어본 뒤 공유기를 재부팅합니다. 연결이 1~2분 끊깁니다. `--dry-run`으로 요청만 볼 수 있습니다.

### call, methods

```console
$ iptime call dhcpd/reservedaddr/show lan
{
 "result": [
  {
   "mac": "AA:BB:CC:00:00:02",
   "ip": "192.168.0.11",
   "desc": "NAS"
  }
 ]
}

$ iptime methods --seen
METHOD                          KIND     STATUS  FIRMWARE  NOTE
admin/auth/info                 read     ok      16.00.0   login policy: auth mode, session timeout, captcha use/tolerance
conn/info                       read     ok      16.00.0   connection-tracking totals per LAN host
...
```

`call`은 공유기의 응답 전체(`{"result": ...}` 또는 `{"error": ...}`)를 출력하고, 오류 응답이면 종료 코드 1을 돌려줍니다. 파라미터는 JSON이고, `lan`처럼 따옴표 없는 단어는 문자열로 보냅니다. 읽기가 아닌 메서드는 `--write`(또는 `--dry-run`)가 있어야 합니다. `iptime methods`는 공유기가 필요 없으며 `--kind read|write|danger|session`, `--seen`으로 거릅니다. STATUS는 `ok`(실제 장비에서 읽기 전용으로 호출해 응답 확인), `absent`(해당 모델이 "Method not found"나 "Config error"로 답함), `used`(예전 수작업 스크립트가 실제 장비에 보낸 쓰기 메서드), `bundle`(관리자 번들에 이름만 있고 우리가 호출한 적 없음)입니다.

### 라이브러리

```python
from iptime_cli import Router

with Router("192.168.0.1", "admin", "change-me") as router:     # 끝나면 로그아웃
    for st in router.stations():                                # 타입 있음: Station
        print(st.ip, st.mac, st.name, st.link)
    print(router.call("firmware/version/latest"))               # 아무 메서드, "result"를 반환
```

```text
192.168.0.10 AA:BB:CC:00:00:01 desktop wired
192.168.0.11 AA:BB:CC:00:00:02 nas wired
192.168.0.20 AA:BB:CC:00:00:03 laptop wireless
192.168.0.21 AA:BB:CC:00:00:04 phone wireless
192.168.0.30 AA:BB:CC:00:00:05 smart-plug wireless
16.010
```

헬퍼: `product()`, `firmware()`, `system()`, `wan()`, `lan()`, `stations()`, `leases()`, `reservations()`, `wifi()`, `port_forwards()`, `remote_admin()`, 쓰기용 `add_port_forward()`, `del_port_forward()`, `reserve()`, `unreserve()`, `set_remote_admin()`, `upgrade_firmware()`, `reboot()`. `call()`은 `result`를 돌려주고 오류 응답이면 `ApiError`를 던집니다. 응답 전체가 필요하면 `call_raw()`를 씁니다. 예외는 모두 `IptimeError`에서 나뉩니다: `ConnectError`, `OldUiError`, `LoginError`(`CaptchaError`, `LockoutError`), `ApiError`, `UpgradeError`. `Router(..., dry_run=True)`는 읽기가 아닌 호출을 보내지 않고 요청 내용만 돌려줍니다.

## 옵션

| 옵션 | 뜻 |
|---|---|
| `--host`, `--user`, `--config 파일` | 접속 설정(위 설정 참고) |
| `--timeout 초` | 요청당 제한 시간, 기본 15 |
| `--insecure` | 자체 서명 https 인증서를 검증하지 않음 |
| `--json` | 표 대신 JSON 출력 |
| `--show-secrets` | 와이파이 비밀번호 표시(기본은 숨김) |
| `--dry-run` | 쓰기 명령에서 요청만 출력하고 보내지 않음 |
| `-y`, `--yes` | 쓰기 전에 묻지 않음 |

종료 코드: `0` 정상, `1` 오류(공유기·로그인·API), `2` 잘못된 사용 또는 잘못된 params JSON.

## 오류 메시지

| 메시지 | 뜻 |
|---|---|
| `old admin UI not supported yet` | 공유기에 `/ui/` 화면이 없거나 JSON으로 답하지 않습니다. 옛 관리자 화면(펌웨어 14.x 이하)입니다 |
| `login failed (wrong user or password?)` | 로그인이 거부되었습니다 |
| `the router asks for a captcha` / `the router blocks logins for now` | 캡차를 요구하거나 실패가 쌓여 로그인을 막았습니다. 잠시 기다리거나 브라우저에서 한 번 로그인하세요 |
| `cannot reach ...` | 주소가 틀렸거나 공유기가 꺼져 있거나, 이 기기가 내부망에 접근할 수 없습니다 |

## 쓰기 명령 안전 수칙

- 쓰기 명령은 항상 먼저 묻습니다. 터미널이 없으면 `--yes` 없이는 거부하고, `--dry-run`은 절대 보내지 않습니다.
- 먼저 `--dry-run`으로 요청을 확인한 뒤 실행하세요.
- `remote-admin on`은 관리 화면을 인터넷에 엽니다. 강한 비밀번호를 쓰거나, 켜지 마세요.
- `port rm`은 이름으로 지우며 이름은 정확히 일치해야 합니다. `dhcp reserve`는 호출 한 번에 MAC 하나, IP 하나입니다.
- `firmware upgrade`는 공유기를 재부팅하고 네트워크를 몇 분 끊습니다. 한적한 시간에 직접 실행하세요(자동 실행 예약은 권하지 않습니다). 공유기의 온라인 업그레이드만 사용합니다.
- 이 버전에서 와이파이 설정은 읽기 전용입니다.
- `iptime call`은 모르는 메서드를 `--write` 없이는 보내지 않습니다.

## 테스트한 범위

| 항목 | 결과 |
|---|---|
| 공유기 | ipTIME A5004NS-M 한 대, 펌웨어 16.00.0 (빌드 2026.09.16) |
| 읽기 명령 (`info`, `clients`, `wan`, `wifi`, `dhcp list`, `port list`, `remote-admin`, `firmware check`, `call`)와 `firmware upgrade --dry-run` | 그 공유기에서 실행 |
| 쓰기 명령 (`port add/rm`, `dhcp reserve/unreserve`, `remote-admin on/off`, `reboot`, `firmware upgrade`) | **함께 들어 있는 가짜 공유기에서만** 실행했고, 이 패키지가 실제 공유기에 보낸 적은 없습니다. 요청 본문은 관리자 화면이 보내는 형식을 따랐습니다. 예전 수작업 스크립트가 같은 포트포워딩·DHCP 고정 할당 본문을 실제 공유기에 보내 동작을 확인했고, `remote-admin off`·`remote-admin on`·`reboot`, 펌웨어 업그레이드 호출 두 개와 진행 단계 값은 관리자 번들에서 읽은 것이라 실제 장비에는 닿은 적이 없습니다 |
| 로그인 실패 | 실제 장비에 잘못된 로그인을 한 번 보냈더니 `{"error": {"code": -31996, "message": "Config error"}}`가 돌아왔습니다. 캡차·잠금 메시지는 보지 못했고, 그 경로는 가짜 공유기로만 확인했으므로 문구는 추정입니다 |
| OS | macOS(파이썬 3.12)는 실제 공유기로, 윈도우 11(파이썬 3.10)과 우분투 24.04(파이썬 3.12)는 PyPI에서 설치해 내장 가짜 공유기로 확인 |
| 확인하지 못한 것 | 윈도우·리눅스에서 실제 공유기, 다른 모델, 다른 16.x 빌드, https 관리 화면, 옛 관리자 화면(오류로 거부), 와이파이 7·메시 모델 |

모델마다 다를 수 있습니다. 테스트한 모델에서는 `system/temperature`, `wireless/mlo/info`, `port/role`, `power/status`, `fan/running`이 없었습니다.

## AI 에이전트용

[AGENTS.md](https://github.com/elfenomenokim/iptime-cli/blob/main/AGENTS.md)를 보세요. 바로 쓸 수 있는 스킬은 `skill/iptime-cli/SKILL.md`에 있습니다.

## 라이선스

MIT.
