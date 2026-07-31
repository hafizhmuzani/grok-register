<div align="center">

[![Grok Register — Toolkit otomatisasi registrasi GUI dan CLI](assets/banner.png)](https://github.com/AaronL725/grok-register)

Grok Register adalah tool Python yang dirancang untuk riset alur otomatisasi, verifikasi lingkungan pengujian, dan pembelajaran pribadi. Proyek ini menyediakan GUI / CLI, empat layanan email sementara, otomatisasi halaman Chromium, penyimpanan akun yang aman, pemulihan pending, pool token grok2api, serta ekspor kredensial CPA xAI OIDC yang opsional.

<p>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="License: MIT"></a>
  <img src="https://img.shields.io/badge/Python-3.9%2B-3776AB.svg" alt="Python 3.9+">
  <img src="https://img.shields.io/badge/Interface-GUI%20%2B%20CLI-success.svg" alt="GUI + CLI">
  <img src="https://img.shields.io/badge/Browser-Chromium%2FChrome-4285F4.svg" alt="Chromium/Chrome">
  <a href="http://makeapullrequest.com"><img src="https://img.shields.io/badge/PRs-welcome-brightgreen.svg" alt="PRs Welcome"></a>
  <a href="https://linux.do"><img src="https://img.shields.io/badge/Join-linux.do-orange" alt="linux.do"></a>
</p>

<p align="center">
 <a href="https://www.star-history.com/aaronl725/grok-register">
  <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/badge?repo=AaronL725/grok-register&theme=dark" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/badge?repo=AaronL725/grok-register" />
   <img alt="Star History Rank" src="https://api.star-history.com/badge?repo=AaronL725/grok-register" />
  </picture>
 </a>
</p>

</div>

---

> [!IMPORTANT]
> Proyek ini hanya digunakan untuk riset alur otomatisasi, verifikasi lingkungan pengujian, dan pembelajaran pribadi. Pengguna harus mematuhi syarat layanan situs target, hukum setempat, dan batasan layanan pihak ketiga. Jangan gunakan proyek ini untuk penyalahgunaan, membatasi akses platform, atau penggunaan komersial tanpa izin.

## Daftar Isi

- [Fitur Saat Ini](#fitur-saat-ini)
- [Alur Kerja](#alur-kerja)
- [Persyaratan Sistem](#persyaratan-sistem)
- [Instalasi](#instalasi)
- [Konfigurasi](#konfigurasi)
- [Cara Menjalankan](#cara-menjalankan)
- [Output & Pemulihan Pending](#output--pemulihan-pending)
- [Stabilitas & Mekanisme Keamanan](#stabilitas--mekanisme-keamanan)
- [Arsitektur Proyek](#arsitektur-proyek)
- [FAQ](#faq)
- [Lisensi](#lisensi)
- [Penghargaan](#penghargaan)
- [Star History](#star-history)

## Fitur Saat Ini

- Menggunakan halaman Chromium / Chrome asli untuk menyelesaikan registrasi, verifikasi captcha, pengisian data, dan perolehan cookie Turnstile & SSO.
- Mendukung empat layanan email:
  - DuckMail
  - YYDS
  - Cloudflare Email Sementara
  - Cloud Mail Mode Kotak Masuk Umum
- Akun yang berhasil langsung ditulis ke `accounts_*.txt`.
- Jika penulisan file hasil utama gagal, secara otomatis ditulis ke `*.pending.jsonl` untuk dipulihkan nanti secara idempoten.
- Mendukung penulisan token SSO ke pool lokal dan remote grok2api.
- Mendukung ekspor kredensial CPA xAI OIDC untuk CLIProxyAPI setelah registrasi berhasil.
- Mendukung percobaan mengaktifkan NSFW setelah registrasi; kegagalan tidak mempengaruhi penyimpanan akun.
- Mendukung restart browser, percobaan ulang jika macet, pergantian email, pembersihan memori berkala, dan pembatalan aman.
- GUI / CLI menampilkan empat status batch:
  - Berhasil
  - Gagal
  - Menunggu Pemulihan
  - Peringatan Pasca-Proses

## Alur Kerja

Alur utama untuk satu akun adalah sebagai berikut:

```text
Buka halaman registrasi
  → Buat email sementara dan kirimkan
  → Polling dan isi kode verifikasi
  → Isi data profil
  → Tunggu cookie SSO
  → Opsional: aktifkan NSFW
  → Simpan akun
  → Opsional: masukkan ke grok2api
  → Opsional: ekspor CPA/OIDC
```

Setelah akun berhasil didaftarkan, pemasukan token atau ekspor CPA termasuk dalam **pasca-proses tambahan**. Kegagalan fitur tambahan hanya menambah "peringatan pasca-proses", tidak mengubah status akun yang sudah tersimpan menjadi registrasi gagal.

## Persyaratan Sistem

- Python **3.9+**
- Google Chrome atau Chromium
- Jaringan yang dapat mengakses halaman registrasi dan API email yang dipilih
- Mode GUI memerlukan Tkinter; jika tidak tersedia, gunakan mode CLI

## Instalasi

Clone repositori:

```bash
git clone https://github.com/hafizhmuzani/grok-register.git
cd grok-register
```

Disarankan membuat virtual environment:

```bash
python -m venv .venv
```

Aktifkan virtual environment:

```bash
# Windows PowerShell
.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate
```

Instal dependensi:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Salin file konfigurasi:

```bash
# macOS / Linux
cp config.example.json config.json

# Windows CMD
copy config.example.json config.json
```

Lalu edit `config.json`. File ini berisi API Key, JWT, proxy, dan kunci layanan remote.

## Konfigurasi

Validasi konfigurasi terbagi menjadi dua lapisan:

1. **Validasi Struktur**: Memeriksa tipe, enum, URL, dan rentang numerik. Saat GUI dimulai, hanya lapisan ini yang dijalankan, sehingga konfigurasi lama yang kehilangan field layanan yang dibutuhkan masih dapat membuka antarmuka untuk diperbaiki.
2. **Validasi Runtime**: Dijalankan saat mengklik "Mulai Registrasi" atau memulai tugas CLI, memeriksa konfigurasi yang diperlukan oleh fitur yang aktif.

### Konfigurasi Dasar

| Konfigurasi | Keterangan |
| --- | --- |
| `email_provider` | `duckmail`, `yyds`, `cloudflare`, atau `cloudmail` |
| `register_count` | Target jumlah batch ini, rentang diatur oleh validasi konfigurasi |
| `proxy` | Proxy registrasi utama, boleh kosong |
| `enable_nsfw` | Apakah mencoba mengaktifkan NSFW setelah registrasi |
| `user_agent` | User-Agent yang digunakan browser dan request |

### DuckMail

| Konfigurasi | Keterangan |
| --- | --- |
| `duckmail_api_key` | API Key DuckMail (opsional) |

### YYDS

| Konfigurasi | Keterangan |
| --- | --- |
| `yyds_api_key` | API Key YYDS |
| `yyds_jwt` | JWT YYDS |

Saat memilih `yyds`, `yyds_api_key` dan `yyds_jwt` minimal harus diisi satu, jika tidak validasi runtime akan langsung menolak.

### Cloudflare Email Sementara

| Konfigurasi | Keterangan |
| --- | --- |
| `cloudflare_api_base` | Alamat dasar API email sementara Cloudflare |
| `cloudflare_api_key` | Kosongkan untuk mode anonim; isi `ADMIN_PASSWORD` untuk mode admin |
| `cloudflare_auth_mode` | `none`, `bearer`, `x-api-key`, `x-admin-auth`, atau `query-key` |
| `cloudflare_path_domains` | Path daftar domain, default `/api/domains` |
| `cloudflare_path_accounts` | Path pembuatan email, default `/api/new_address` |
| `cloudflare_path_token` | Path token, default `/api/token` |
| `cloudflare_path_messages` | Path daftar pesan masuk, default `/api/mails` |
| `defaultDomains` | Domain penerima default; beberapa domain dipisahkan koma dan digunakan bergantian |

#### Mode Pembuatan Anonim

```json
{
  "email_provider": "cloudflare",
  "cloudflare_api_base": "https://domain-worker-api-anda",
  "cloudflare_api_key": "",
  "cloudflare_auth_mode": "none",
  "cloudflare_path_domains": "/api/domains",
  "cloudflare_path_accounts": "/api/new_address",
  "cloudflare_path_token": "/api/token",
  "cloudflare_path_messages": "/api/mails",
  "defaultDomains": "example.com"
}
```

#### Mode Pembuatan Admin

Ketika endpoint anonim `/api/new_address` terbatas oleh Turnstile, gunakan:

```json
{
  "email_provider": "cloudflare",
  "cloudflare_api_base": "https://domain-worker-api-anda",
  "cloudflare_api_key": "ADMIN_PASSWORD anda",
  "cloudflare_auth_mode": "x-admin-auth",
  "cloudflare_path_accounts": "/admin/new_address",
  "cloudflare_path_messages": "/api/mails",
  "defaultDomains": "example.com"
}
```

Password Admin hanya digunakan untuk membuat email. Membaca pesan tetap menggunakan JWT email yang dikembalikan oleh endpoint pembuatan.

Gunakan skrip debug untuk memverifikasi endpoint:

```bash
python cf_mail_debug.py \
  --api-base "https://domain-worker-api-anda" \
  --auth-mode x-admin-auth \
  --api-key "ADMIN_PASSWORD anda" \
  --create-path /admin/new_address \
  --domain "example.com"
```

### Cloud Mail Mode Kotak Masuk Umum

| Konfigurasi | Keterangan |
| --- | --- |
| `cloudmail_api_base` | Alamat dasar situs Cloud Mail |
| `cloudmail_public_token` | Token API Kotak Masuk Umum |
| `cloudmail_domains` | Domain kotak masuk umum, beberapa domain dipisahkan koma |
| `cloudmail_path_messages` | Default `/api/public/emailList` |

Contoh:

```json
{
  "email_provider": "cloudmail",
  "cloudmail_api_base": "https://domain-Cloud-Mail-anda",
  "cloudmail_public_token": "Token API Publik",
  "cloudmail_domains": "example.com,example.net",
  "cloudmail_path_messages": "/api/public/emailList"
}
```

Mode Cloud Mail langsung membuat alamat acak, tidak membuat akun email terlebih dahulu. Token Publik hanya dibaca dari `config.json`, tidak ditulis sebagai kredensial email ke `mail_credentials.txt`.

### Pool Token grok2api

| Konfigurasi | Keterangan |
| --- | --- |
| `grok2api_auto_add_local` | Apakah menulis ke pool token lokal |
| `grok2api_local_token_file` | Path `token.json` lokal; kosongkan untuk menggunakan path default proyek |
| `grok2api_pool_name` | `ssoBasic` atau `ssoSuper` |
| `grok2api_auto_add_remote` | Apakah menulis ke pool token remote |
| `grok2api_remote_base` | Alamat dasar situs, `/admin`, atau `/admin/api` |
| `grok2api_remote_app_key` | App key API manajemen remote versi lama |
| `grok2api_remote_admin_username` | Username admin `chenyme/grok2api` versi baru |
| `grok2api_remote_admin_password` | Password admin `chenyme/grok2api` versi baru |
| `grok2api_allow_legacy_full_save` | Apakah mengizinkan fallback penyimpanan penuh versi lama; default mati |

Pemasukan remote otomatis memilih versi berdasarkan kredensial: mengisi `app_key` menggunakan `/tokens/add` versi lama; mengisi username dan password admin akan mengimpor ke Grok Web melalui `/api/admin/v1/accounts/web/import` versi baru. Dua set kredensial tidak bisa diisi bersamaan. Request manajemen versi baru default langsung terhubung, alamat remote wajib menggunakan HTTPS, alamat lokal bisa menggunakan HTTP. Penyimpanan penuh versi lama default dimatikan untuk menghindari overwrite konkuren.

```json
{
  "grok2api_auto_add_remote": true,
  "grok2api_remote_base": "https://domain-grok2api-anda",
  "grok2api_remote_app_key": "",
  "grok2api_remote_admin_username": "admin",
  "grok2api_remote_admin_password": "password admin anda",
  "grok2api_pool_name": "ssoBasic",
  "grok2api_allow_legacy_full_save": false
}
```

### CPA / Ekspor xAI OIDC

| Konfigurasi | Keterangan |
| --- | --- |
| `cpa_export_enabled` | Apakah mengekspor kredensial CPA xAI OIDC setelah registrasi berhasil |
| `cpa_auth_dir` | Direktori output, default `./cpa_auths` |
| `cpa_copy_to_hotload` | Apakah menyalin ke auth-dir CLIProxyAPI |
| `cpa_hotload_dir` | Direktori hotload; wajib diisi hanya jika ekspor aktif dan salin aktif |
| `cpa_base_url` | API Base URL dalam kredensial CPA |
| `cpa_proxy` | Proxy khusus CPA; kosongkan untuk kembali ke `proxy` utama |
| `cpa_headless` | Apakah browser CPA headless; default disarankan `false` |
| `cpa_force_standalone` | Apakah menggunakan sesi browser CPA independen |
| `cpa_mint_timeout_sec` | Timeout keseluruhan otorisasi browser |
| `cpa_mint_cookie_inject` | Apakah menyuntikkan cookie yang sudah diperoleh ke sesi CPA |
| `cpa_oidc_request_timeout_sec` | Timeout request Device Authorization |
| `cpa_oidc_poll_timeout_sec` | Timeout request polling token sekali |
| `api_reverse_tools` | Direktori paket `cpa_xai` eksternal (opsional) |

Konfigurasi minimal:

```json
{
  "cpa_export_enabled": true,
  "cpa_auth_dir": "./cpa_auths",
  "cpa_base_url": "https://cli-chat-proxy.grok.com/v1",
  "cpa_proxy": "",
  "cpa_headless": false,
  "cpa_force_standalone": true,
  "cpa_mint_cookie_inject": true
}
```

Browser CPA langsung menggunakan kembali opsi Chromium dari `browser_runtime.py` dan jembatan proxy dari `cpa_xai/proxyutil.py`, tidak mengimpor balik program utama atau membuat salinan kedua status global modul utama.

## Cara Menjalankan

### GUI

```bash
python grok_register_ttk.py
```

Saat GUI dimulai, konfigurasi dibaca dan validasi struktur dijalankan. Setelah mengisi konfigurasi, klik "Mulai Registrasi" untuk menjalankan validasi runtime penuh, menyimpan konfigurasi sekali saja, lalu memulai thread latar belakang.

Sebelum setiap batch baru dimulai, keempat statistik (berhasil, gagal, menunggu pemulihan, dan peringatan pasca-proses) akan di-reset ke nol.

### CLI

Perintah berikut memiliki efek yang sama:

```bash
python grok_register_ttk.py cli
python grok_register_ttk.py start
python grok_register_ttk.py --cli
```

CLI membaca `register_count` dari `config.json`, setelah lolos validasi runtime akan menampilkan:

```text
> start
```

Ketik `start` untuk memulai. Tekan `Ctrl+C` untuk meminta berhenti dan menjalankan pembersihan akhir.

> CLI hanya tidak membuka Tk GUI, proses registrasi tetap membuka Chromium / Chrome.

### Memulihkan Hasil Pending

```bash
python grok_register_ttk.py retry-pending <file_pending> [file_output]
```

Contoh:

```bash
python grok_register_ttk.py retry-pending accounts_20260715_120000.txt.pending.jsonl
```

Menentukan file output lain:

```bash
python grok_register_ttk.py retry-pending \
  accounts_20260715_120000.txt.pending.jsonl \
  recovered_accounts.txt
```

Program akan menolak menjadikan file input pending sebagai file output yang sama.

## Output & Pemulihan Pending

Selama proses berjalan, file-file berikut mungkin dihasilkan:

| File | Isi |
| --- | --- |
| `accounts_*.txt` | Akun, password, dan token SSO yang berhasil disimpan |
| `mail_credentials.txt` | Alamat email sementara dan kredensial email |
| `*.pending.jsonl` | Akun yang sudah didaftarkan tetapi file hasil utama gagal ditulis |
| `*.pending.jsonl.lock` | Kunci eksklusif pemulihan pending |
| `token.json` (lokal) | Pool grok2api lokal opsional |
| `cpa_auths/xai-*.json` | Kredensial CPA xAI OIDC opsional |
| `cpa_auths/cpa_auth_failed.txt` | Catatan kegagalan ekspor CPA |
| `screenshots/` | Screenshot debug kegagalan browser CPA |

Pemulihan pending memiliki perlindungan berikut:

- Menggunakan `filelock` untuk mengunci eksklusif file pending yang sama;
- Membaca, memulihkan, menulis ulang, atau menghapus file pending semuanya dilakukan dalam kunci;
- File hasil utama melakukan deduplikasi berdasarkan `email+sso`;
- Catatan yang sudah ada langsung dianggap berhasil dipulihkan;
- File pending menggunakan file sementara dan penggantian atomik;
- Path input dan output yang sama akan ditolak.

Oleh karena itu, jika proses terputus di antara "akun sudah ditambahkan, pending belum diperbarui", menjalankan pemulihan ulang tidak akan menulis duplikat akun yang sama.

## Stabilitas & Mekanisme Keamanan

### Alur Batch

- Ketika verifikasi email gagal, dapat diganti dengan email lain untuk dicoba ulang.
- Ketika halaman macet, slot akun saat ini akan dicoba ulang hingga batas baru dihitung sebagai gagal.
- Browser di-restart atau dibuat ulang di antara setiap akun.
- Setiap 5 akun yang berhasil, pembersihan runtime dijalankan secara default.
- Kegagalan pembersihan berkala hanya mencatat peringatan, tidak mengubah statistik akun.
- Saat pembatalan oleh pengguna di antara akun, status batch `cancelled` diatur dan berakhir dengan normal.
- Pembersihan akhir yang gagal tidak menimpa pengecualian tugas asli.
- Pengecualian observer GUI tidak menghentikan alur batch.

### Penulisan File

- Konfigurasi, pool token lokal, dan pembaruan pending menggunakan file sementara dengan penggantian atomik.
- Pool token lokal menggunakan filelock; JSON yang rusak tidak akan ditimpa secara diam-diam.
- Token yang sudah ada akan dideduplikasi.

### Isolasi Pasca-Proses

- Setelah penyimpanan akun utama selesai, pemasukan token dan ekspor CPA masing-masing menangkap pengecualian.
- Kegagalan satu langkah pasca-proses tidak menghalangi langkah lainnya dijalankan.
- Kegagalan pasca-proses tidak mengubah klasifikasi akun menjadi registrasi gagal.

## Arsitektur Proyek

```text
.
├── grok_register_ttk.py       # GUI, CLI, entri parameter, dan lapisan kompatibilitas
├── registration_flow.py       # Satu-satunya entri orkestrasi batch GUI / CLI
├── app_config.py              # Konfigurasi default, muat simpan, validasi struktur & runtime
├── account_outputs.py         # Output akun, pending, pool token, dan penulisan atomik
├── mail_service.py            # DuckMail, YYDS, Cloudflare, Cloud Mail
├── browser_runtime.py         # HTTP, proxy, dan opsi Chromium
├── registration_browser.py    # Siklus hidup browser registrasi utama & otomatisasi halaman
├── cf_mail_debug.py           # CLI debug email Cloudflare
├── cpa_export.py              # Entri kompatibilitas ekspor CPA/OIDC
├── cpa_xai/
│   ├── browser_session.py     # Pembuatan, penggunaan ulang, cookie & pembersihan browser CPA
│   ├── browser_confirm.py     # Login, halaman otorisasi, & orkestrasi mint
│   ├── oauth_device.py        # Device Authorization & polling token
│   ├── proxyutil.py           # Implementasi jembatan proxy terotentikasi satu-satunya proyek
│   ├── mint.py                # Alur credential mint
│   ├── schema.py              # Struktur output CPA
│   └── writer.py              # Penulisan file kredensial
├── config.example.json        # Contoh konfigurasi lengkap
├── requirements.txt           # Dependensi Python
├── tests/                     # Unit test dan regresi kompatibilitas
├── turnstilePatch/            # Sumber daya ekstensi browser
├── assets/                    # Aset README
└── README.md
```

## FAQ

### Mengapa CLI tetap membuka browser?

CLI hanya menghilangkan Tk GUI. Interaksi halaman registrasi, Turnstile, pengiriman captcha, dan perolehan cookie SSO tetap bergantung pada lingkungan Chromium asli.

### Bagaimana jika GUI tidak bisa dimulai?

Pastikan Python saat ini memiliki Tkinter. Distribusi Linux mungkin perlu menginstal paket sistem secara terpisah, misalnya `python3-tk`. Bisa juga menggunakan:

```bash
python grok_register_ttk.py cli
```

### Mengapa GUI tetap bisa dibuka meski konfigurasi tidak lengkap?

Ini adalah perilaku yang diharapkan. Saat GUI dimulai hanya menjalankan validasi struktur, memudahkan perbaikan konfigurasi layanan di antarmuka; validasi runtime baru dijalankan saat mengklik mulai.

### Mengapa jumlah akun berhasil lebih sedikit dari jumlah registrasi yang selesai?

"Berhasil" berarti akun telah selesai didaftarkan dan file hasil utama sudah tersimpan. Akun yang selesai didaftarkan tetapi gagal menulis file utama akan ditampilkan di "Menunggu Pemulihan", dan ditulis ke file pending.

### Apa itu peringatan pasca-proses?

Akun sudah tersimpan, tetapi setidaknya satu dari pemasukan grok2api atau ekspor CPA gagal. Akun itu sendiri tetap terhitung berhasil, tidak perlu didaftarkan ulang.

### Apakah kegagalan mengaktifkan NSFW menyebabkan akun hilang?

Tidak. NSFW adalah langkah opsional, kegagalan akan dicatat sebagai peringatan dan akun tetap disimpan.

### Mengapa remote grok2api menolak penyimpanan penuh versi lama?

Penyimpanan penuh baca-tulis-ubah dalam lingkungan multi-proses berpotensi menimpa token yang baru saja ditulis oleh instance lain. Proyek ini secara default hanya menerima antarmuka inkremental; saat fallback lama secara eksplisit diizinkan, tetap memerlukan ETag dan menggunakan penulisan bersyarat.

### Mengapa direktori hotload CPA bisa dimulai tanpa konfigurasi?

`cpa_hotload_dir` hanya wajib diisi ketika `cpa_export_enabled=true` dan `cpa_copy_to_hotload=true` keduanya aktif.

## Lisensi

[MIT](LICENSE).

## Penghargaan

Terima kasih kepada [linux.do](https://linux.do) — komunitas teknologi yang aktif tempat proyek ini dibagikan dan didiskusikan.

## Star History

<a href="https://www.star-history.com/?repos=AaronL725%2Fgrok-register&type=date&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/chart?repos=AaronL725/grok-register&type=date&theme=dark&legend=top-left&sealed_token=uCM--S2xEp0n8rFUZHUg6wUJOgYcfO4XEVCIF9UZAT04YjL9YsMEOVOGAOlQfqwsoS7cQef0Rwc1cYCY4lAmTuMmcg-hKzNnx1A7KNekuCXQotFd4YifLIkvJWOEy5vxiREJX80Mwxbr8F-3GfCv0utIsQz_iq19nS57svUqwv0mSosV8OTxqXTLjmsI" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/chart?repos=AaronL725/grok-register&type=date&legend=top-left&sealed_token=uCM--S2xEp0n8rFUZHUg6wUJOgYcfO4XEVCIF9UZAT04YjL9YsMEOVOGAOlQfqwsoS7cQef0Rwc1cYCY4lAmTuMmcg-hKzNnx1A7KNekuCXQotFd4YifLIkvJWOEy5vxiREJX80Mwxbr8F-3GfCv0utIsQz_iq19nS57svUqwv0mSosV8OTxqXTLjmsI" />
   <img alt="Star History Chart" src="https://api.star-history.com/chart?repos=AaronL725/grok-register&type=date&legend=top-left&sealed_token=uCM--S2xEp0n8rFUZHUg6wUJOgYcfO4XEVCIF9UZAT04YjL9YsMEOVOGAOlQfqwsoS7cQef0Rwc1cYCY4lAmTuMmcg-hKzNnx1A7KNekuCXQotFd4YifLIkvJWOEy5vxiREJX80Mwxbr8F-3GfCv0utIsQz_iq19nS57svUqwv0mSosV8OTxqXTLjmsI" />
 </picture>
</a>
