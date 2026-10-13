# SR9900 USB Ethernet no Windows on ARM (ARM64)

Como fazer funcionar a placa de rede **CoreChip SR9900** (USB 2.0 10/100) de uma dock/hub USB em notebooks **Windows 11 ARM64 (Snapdragon)** sem escrever driver novo.

O fabricante só distribui driver para x86/x64. Este repositório mostra como trocar o chip do modo "CD-ROM de driver" para o modo placa de rede e usar o driver **Realtek RTL8152 ARM64** que já vem no Windows.

> **Resultado:** link de 100 Mbps full duplex, DHCP, DNS e internet funcionando, com **0 erros e 0 descartes** de pacote no teste.

---

## Sumário

- [O problema](#o-problema)
- [Causa](#causa)
- [Solução rápida](#solução-rápida)
- [Ambiente testado](#ambiente-testado)
- [Especificação do equipamento (dock/hub)](#especificação-do-equipamento-dockhub)
- [Detalhes técnicos](#detalhes-técnicos)
- [Validação](#validação)
- [Solução de problemas](#solução-de-problemas)
- [Referências](#referências)

---

## O problema

Na primeira conexão da dock, o chip de rede não aparece como placa de rede. Ele aparece como uma **unidade de CD virtual** ("CoreChip USB CD-ROM") com o instalador do driver:

```
E:\AUTORUN.INF
E:\CoreChip.ico
E:\SR9900_SFX_207.exe     (driver SR9900 v2.0.7.0, 12/07/2023, somente x86/x64)
```

No Windows ARM64, o instalador x64 até abre (emulação), mas o **driver de kernel x64 (`SR9900.sys`) não carrega**. O Windows on ARM só aceita drivers de kernel ARM64 nativos. Não existe versão ARM64 do driver da CoreChip.

## Causa

1. **Modo ZeroCD:** ao ser ligado, o SR9900 se apresenta como armazenamento em massa/CD-ROM (`USB\VID_0FE6&PID_9910`). Só vira placa de rede (`USB\VID_0FE6&PID_9900`) quando recebe um comando SCSI específico. Quem envia esse comando é o `install.exe` do pacote oficial.
2. **Compatibilidade com o RTL8152:** o SR9900 é compatível com o **Realtek RTL8152**:
   - Um patch do kernel Linux (jun/2026) adiciona `0fe6:9900` ao driver `r8152`, com 94 Mbps e zero perda de pacotes.
   - O caminho do PDB embutido no instalador oficial é `e:\8152\sr9800b\...`, o que indica que o driver da CoreChip saiu do código da Realtek.
   - O chip se identifica com revisão `REV_2000`, a mesma das variantes do RTL8152B no INF da Realtek.
3. O Windows 11 ARM64 **já traz** o driver Realtek USB FE/GbE ARM64 (`rtuarm64w10.inf` / `rtucx21arm64.inf`). Ele só não é escolhido automaticamente porque o VID/PID da CoreChip não está no INF.

## Solução rápida

### Passo 1: trocar o chip para o modo placa de rede

Requisito: Python 3 para Windows ARM64 ou x64. **Não precisa de Administrador.**

```powershell
python sr9900_modeswitch.py
```

O script acha sozinho a unidade "CoreChip USB CD-ROM" e envia o comando de troca. Para indicar a letra manualmente: `python sr9900_modeswitch.py E`.

Saída esperada:

```
Enviando comando de troca de modo para E:
DeviceIoControl ok=True lastError=0 scsiStatus=0
```

Em poucos segundos a unidade de CD some e aparece **"USB 10/100 LAN"** sem driver em *Outros dispositivos*.

### Passo 2: associar o driver Realtek ARM64 nativo (como Administrador)

No **Gerenciador de Dispositivos**:

1. Clique com o botão direito em **"USB 10/100 LAN"** → **Atualizar driver**
2. **Procurar drivers no meu computador** → **Permitir que eu escolha em uma lista de drivers disponíveis**
3. Escolha **Adaptadores de rede** → Avançar
4. **Desmarque** "Mostrar hardware compatível"
5. Fabricante: **Realtek**. Modelo: **Realtek(R) USB FE Family Controller**
6. Confirme o aviso de compatibilidade não verificada (**Sim**)

Se der erro (código 10), repita escolhendo **"Realtek USB FE Family Controller"** (sem o "(R)").

### Persistência

No teste, depois de desplugar e plugar a dock de novo, **o chip voltou direto em modo placa de rede** (PID_9900). O modo CD não apareceu mais e o driver continuou associado. Então a troca de modo só precisa ser feita **uma vez**. Se a dock voltar a aparecer como CD, basta rodar o Passo 1 de novo.

---

## Ambiente testado

| Item | Valor |
|---|---|
| Notebook | Lenovo ThinkPad X13s Gen 1 (`21BY001FBR`) |
| Processador | Qualcomm Snapdragon 8cx Gen 3 @ 3.0 GHz (ARM64) |
| Sistema | Windows 11 Pro 25H2, build 10.0.26200 |
| Driver usado | `rtuarm64w10.inf` / `rtuarm64w10.sys` v10.38.117.2020 (inbox, assinado pela Microsoft) |
| Driver alternativo disponível | `rtucx21arm64.inf` v11.4.0211.2022 (inbox) |
| Python | 3.14 |

---

## Especificação do equipamento (dock/hub)

### Controlador de rede

| Item | Valor |
|---|---|
| Chip | **CoreChip (CoreChips / Supereal) SR9900** |
| Tipo | Controlador USB 2.0 → Fast Ethernet (MAC + PHY + controlador USB + memória embutida), IEEE 802.3u |
| Velocidade | 10/100 Mbps, full duplex |
| ID em modo CD (ZeroCD) | `USB\VID_0FE6&PID_9910`, armazenamento em massa "CoreChip USB CD-ROM" (`USBSTOR\CDROM&VEN_CORECHIP&PROD_USB_CD-ROM&REV_2.00`) |
| ID em modo rede | `USB\VID_0FE6&PID_9900&REV_2000`, "USB 10/100 LAN" |
| IDs compatíveis | `USB\Class_FF&SubClass_FF&Prot_00` (classe vendor-specific) |
| Prefixo do MAC | `00:E6:02` |
| Driver oficial | SR9900 v2.0.7.0 (12/07/2023), somente x86/x64; sem versão ARM64 |
| Driver que funciona no ARM64 | Realtek RTL8152 ("Realtek(R) USB FE Family Controller"), inbox do Windows |

### Topologia USB observada

A dock usa hubs **USB 2.0**: todas as portas e a placa de rede dividem a banda de 480 Mbps.

```
USB Root Hub (USB 3.0) do notebook
└── 214B:7250  "USB2.0 HUB"                     (hub de entrada)
    ├── 046D:0A8F  Logi USB Headset              (periférico)
    └── 214B:7250  "USB2.0 HUB"                  (hub interno)
        ├── 0FE6:9900  CoreChip SR9900 – USB 10/100 LAN   ← placa de rede
        ├── 1908:0226  Leitor de cartão (Generic Mass-Storage)
        └── 05E3:0606  Genesys Logic "USB Hub 2.0"
            ├── 1A2C:0E24  Teclado/receptor USB  (periférico)
            ├── 17EF:6123  Teclado/mouse Lenovo  (periférico)
            └── 05E3:0606  Genesys Logic "USB Hub 2.0"
```

| VID:PID | Componente | Fabricante do chip |
|---|---|---|
| `214B:7250` | Hub USB 2.0 (2 em cascata) | Huasheng Electronics |
| `05E3:0606` | Hub USB 2.0 | Genesys Logic |
| `1908:0226` | Leitor de cartões SD/microSD | GEMBIRD / Generalplus |
| `0FE6:9900` / `0FE6:9910` | Ethernet 10/100 / CD virtual | CoreChip (ICS Advent VID) |

> Os periféricos marcados (headset, teclado, mouse) estavam ligados durante o levantamento e não fazem parte da dock.

---

## Detalhes técnicos

### Como o comando de troca de modo foi descoberto

O `SR9900_SFX_207.exe` é um SFX extraível com 7-Zip, sem precisar executá-lo:

```
Setup.exe                 (InstallStart: chama .\install.exe)
drivers\x64\install.exe   (faz a troca de modo e instala o INF)
drivers\x64\SR9900.inf / SR9900.sys / sr9900.cat
drivers\x86\...
```

No `install.exe` (x64) aparecem `CreateFileA("\\.\A:"...)`, `DeviceIoControl` e o código `0x0004D014` (`IOCTL_SCSI_PASS_THROUGH_DIRECT`). Também aparecem as strings de inquiry usadas para achar o drive: `Realtek `, `CoreChip`, `USB CD-ROM`. A desmontagem da montagem da estrutura `SCSI_PASS_THROUGH_DIRECT` mostra estes valores:

| Campo | Valor |
|---|---|
| `Length` | `0x38` (sizeof SPTD x64) |
| `TargetId` | 1 |
| `CdbLength` | 16 |
| `SenseInfoLength` | 24 |
| `DataIn` | 2 (`SCSI_IOCTL_DATA_UNSPECIFIED`) |
| `DataTransferLength` | 0 |
| `TimeOutValue` | 5 s |
| `SenseInfoOffset` | `0x3C` |
| **`Cdb`** | **`E0 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00`** |

O comando de troca é o **opcode SCSI vendor `0xE0`**, sem fase de dados. O [`sr9900_modeswitch.py`](sr9900_modeswitch.py) reproduz isso em Python puro (`ctypes`, sem dependências). Ele roda nativo em ARM64 e não precisa de privilégio elevado.

Para referência no Linux (usb_modeswitch), a mensagem equivalente seria um CBW de mass storage com CDB `E0` de 16 bytes. Não há entrada oficial para `0fe6:9910` no `usb_modeswitch-data`.

### Por que não escrever um driver novo

- O hardware já fala o protocolo do RTL8152, e a Realtek/Microsoft já fornecem um driver ARM64 **assinado**.
- Um driver próprio exigiria assinatura de kernel (atestação da Microsoft via Partner Center) ou o modo de teste (`testsigning`) ligado, o que enfraquece a segurança da máquina.
- A solução não modifica nem redistribui nenhum driver: só associa manualmente um driver inbox assinado a um VID/PID que ele não lista.

---

## Validação

Testes feitos com o cabo conectado:

| Teste | Resultado |
|---|---|
| Status do dispositivo | OK, `CM_PROB_NONE` |
| Link | 100 Mbps, full duplex |
| DHCP / DNS | IPv4 obtido, resolução de nomes OK |
| Ping no gateway (20×) | 20/20, ~0,1 ms |
| Ping 8.8.8.8 (10×) | 10/10, ~25 ms |
| Download (curl, 50 MB) | ~66 Mbps |
| Upload (curl) | ~40 Mbps |
| Erros / descartes Rx/Tx | 0 / 0 / 0 / 0 |
| Log de eventos (USB/NDIS/Realtek) | nenhum erro ou aviso |
| Desplugar e plugar de novo | Volta direto em modo rede; conectividade 3–4 s após a enumeração |

Comandos úteis para checar:

```powershell
Get-PnpDevice -PresentOnly | ? InstanceId -match 'VID_0FE6'
Get-NetAdapter | ? InterfaceDescription -match 'Realtek'
Get-NetAdapterStatistics -Name 'Ethernet 2'
```

---

## Solução de problemas

| Sintoma | Ação |
|---|---|
| Ainda aparece "CoreChip USB CD-ROM" | Rode `python sr9900_modeswitch.py` |
| Script diz que não encontrou a unidade | O chip já está em modo rede; confira `Get-PnpDevice` por `PID_9900` |
| "Ejetar" pelo Explorer não troca o modo | Esperado: o eject padrão não envia o opcode `0xE0` |
| Código 10 após escolher o driver | Use o outro modelo Realtek FE ("Realtek USB FE Family Controller") |
| Demora para reconhecer ao plugar / porta USB some por instantes | É a enumeração USB da dock (hubs USB 2.0 em cascata), não o driver. Use uma porta direta do notebook e evite hubs extras. |
| Velocidade abaixo de 100 Mbps | O teto é Fast Ethernet; a banda USB 2.0 também é dividida com as outras portas da dock |

---

## Referências

- [PATCH] r8152: add vendor/device ID for CoreChips SR9900 (LKML, jun/2026): https://lkml.rescloud.iu.edu/hypermail/linux/kernel/2606.1/12591.html
- Datasheet CoreChips SR9900 (LCSC): https://wmsc.lcsc.com/wmsc/upload/file/pdf/v2/lcsc/1912111437_CoreChips-SR9900_C403645.pdf
- Driver oficial SR9900 (somente x86/x64): https://oemdrivers.com/network-corechip-sr9900-usb2-0-adapter
- Microsoft: `IOCTL_SCSI_PASS_THROUGH_DIRECT`: https://learn.microsoft.com/windows-hardware/drivers/ddi/ntddscsi/ni-ntddscsi-ioctl_scsi_pass_through_direct

---

## Aviso

Use por sua conta e risco. O script só envia o mesmo comando que o instalador oficial do fabricante envia. Este repositório **não** redistribui drivers da CoreChip nem da Realtek.
