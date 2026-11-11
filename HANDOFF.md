# HANDOFF: edu-radar

Dokumen ini untuk Claude Code di akun baru. Baca habis sebelum bertindak. Kode sudah jadi dan lolos tes offline. Sisa kerja = setup dan verifikasi di dunia nyata.

## 1. Tujuan
- Notifikasi otomatis info pendidikan SMA dan pra-kuliah Indonesia ke Discord.
- Cakupan: SNPMB, UTBK-SNBT, SNBP, KIP Kuliah, PTKIN, kedinasan, TKA, kebijakan, jadwal PTN.
- Target: tahu kurang dari 3 jam setelah kabar muncul.
- Syarat: murah, perawatan rendah, tanpa server, tanpa DB, tanpa LLM.

## 2. Preferensi pemilik (wajib diikuti saat membalas)
- Bahasa Indonesia informal (gw/lo boleh dipahami). Balasan ringkas, terstruktur, bullet.
- Jangan pernah pakai tanda em dash.
- Jangan pakai kata "Verdict". Pakai "intinya" atau "kesimpulannya".
- Pakai gaya caveman (terse) dan stop-slop untuk teks.
- File dan kode ditulis penuh, bukan potongan.

## 3. Arsitektur (sudah jadi)
- `main.py`: satu skrip. Ambil semua sumber paralel, cek robots.txt, diff, filter, kirim Discord.
- `sources.yml`: semua sumber dan filter. Tambah sumber tanpa ubah kode.
- `.github/workflows/run.yml`: jalan di GitHub Actions. State di branch `state` (1 commit, force push).
- `requirements.txt`: versi dipin.
- Pemicu: cron-job.org (workflow_dispatch tiap 15 menit), cron GitHub tiap jam sebagai cadangan.
- Monitor hidup: healthchecks.io (`HC_URL`), skrip ping tiap run sukses.
- Discord 3 channel: `#resmi` (RESMI, PTN), `#berita` (BERITA), `#sistem` (alert sumber rusak/pulih).
- Secrets: `DISCORD_WEBHOOK_RESMI`, `DISCORD_WEBHOOK_BERITA`, `DISCORD_WEBHOOK_SISTEM`, `HC_URL`.
- Repo publik. Secrets hanya di GitHub Secrets.

## 4. Aturan perilaku (sudah diimplementasi dan dites)
- Run pertama per sumber = seed diam. Sumber baru yang ditambah nanti juga seed diam.
- RESMI dan PTN: semua perubahan dikirim (diff baris, bukan seluruh halaman).
- BERITA: hanya yang lolos filter.
- Filter: lolos kalau kena kata inti, atau (kata konteks pendidikan DAN kata peristiwa). Kata negatif membuang.
- Teks yang dicek filter: judul + deskripsi + slug URL.
- Dedup: guid per feed, plus kemiripan judul lintas media (70 karakter ternormalisasi).
- Sumber gagal atau kosong 3x berturut-turut: alert #sistem, sekali. Pulih: pesan pulih.
- Kirim Discord gagal: item tidak ditandai terlihat, dicoba lagi run berikutnya.
- robots.txt dilarang: sumber dilewati dan masuk jalur alert.
- Batas 15 notif per sumber per run, sisanya diringkas satu pesan.
- `allowed_mentions` kosong, jadi teks berita tidak bisa memicu @everyone.
- Poll rata 15 menit untuk semua sumber (keputusan pemilik).

## 5. Sumber
### RESMI (8 aktif, semua belum dites dari IP Actions)
- snpmb.id: `/jadwal-penting` (teks), `/unduhan` (links), `/terkini` (links), `/snbp/kuota-sekolah` (teks)
- kip-kuliah.kemdiktisaintek.go.id (teks). Awas: URL gambar bertanda tangan bisa bikin alarm palsu. Pakai `ignore_regex` bila perlu.
- kemdiktisaintek.go.id news (links, filter `edu`)
- span.ptkin.ac.id dan um.ptkin.ac.id (belum pernah dibaca langsung)
- Tidak dipantau: Kemendikdasmen/TKA/pusmendik (bot diblokir atau daftar via JavaScript).

### PTN top 20 (21 entri aktif, 7 kampus nonaktif)
- Aktif: UNY, UGM (v26 dan pengawas v27), UI, ITB, IPB, ITS, UNAIR, UNDIP, UNS, USU, UNNES, UNSOED, UNAND.
- URL aktif diambil dari navigasi situs resmi yang terbaca lewat fetch. Isi halaman belum dites diff.
- Nonaktif (`enabled: false` + `todo` di sources.yml):
  - UNPAD `smup.unpad.ac.id`: fetch error
  - UNHAS `regpmb.unhas.ac.id`: server error
  - UNSRI `sm.unsri.ac.id`: fetch error
  - UPI `pmb.upi.edu`: halaman JavaScript, isi kosong tanpa render
  - UNJ `pendaftaran.unj.ac.id`: robots.txt melarang. Jangan dinyalakan.
  - UB: portal penerimaan belum ditemukan
  - UNEJ: portal SEMMABA belum ditemukan
- Path bertahun: UGM `v26`/`v27` dan UNNES `tanggal-penting-admisi-2026`. Ganti tiap musim.

### BERITA RSS (12 aktif)
- Lapis A (kanal pendidikan, filter `edu`): detikEdu `https://www.detik.com/edu/rss`
- Lapis B (induk/nasional, filter `strict`): Antara terkini, Okezone (host edukasi pakai filter `edu`), detikNews, CNN Indonesia nasional, Republika, Liputan6, Viva, SINDOnews
- Prioritas rendah (tetap dipakai atas permintaan pemilik): BBC Indonesia, CNBC Indonesia, Tempo nasional
- Alasan ambil feed induk: berita relevan bisa muncul di luar kanal edu.
- Dibuang: Tribunnews (mati sejak 2026-11-08), Kompas (RSS dilarang robots, Telegram tidak resmi dan mati), Metro TV, tvOne, Media Indonesia, Kaskus, path lama Okezone.
- Belum dicoba: JPNN (`jpnn.com/index.php?mib=rss`), kumparan, Kompas lewat Google News `site:kompas.com` (akses dari IP Actions belum diuji).

## 6. Status tes
- Lolos offline (server lokal): seed diam, filter inti/konteks/negatif, dedup lintas feed, diff halaman, `ignore_regex`, `watch_appear`, alert 3x gagal sekali saja, sumber `enabled: false` tidak disentuh, robots melarang, kirim gagal lalu retry, state stabil saat tidak ada perubahan.
- BELUM dites: semua akses jaringan nyata. Sesi pembuat tidak bisa akses internet dari shell, jadi tidak ada satu pun sumber yang dibaca langsung oleh `main.py`.
- Hasil cek via alat fetch (bisa basi): feed lain sehat, Tribunnews mati. Jangan percaya angka "segar" tanpa cek dari Actions.

## 7. Langkah lanjut (urut)
1. Buat repo publik, upload isi paket ini. Cabang default `main`.
2. Buat 3 webhook Discord (#resmi, #berita, #sistem). Simpan sebagai Secrets.
3. (Opsional) buat check di healthchecks.io: period 30 menit, grace 30 menit. Simpan `HC_URL`.
4. Settings > Actions > General > Workflow permissions: Read and write.
5. Run manual sekali (seed). Buka log. Catat sumber yang `gagal` atau `robots.txt melarang`.
6. Perbaiki sumber rusak di `sources.yml` (URL salah, perlu `ignore_regex`, atau matikan).
7. Cek kesegaran tiap RSS dari log: pastikan item baru benar-benar baru, bukan cache lama.
8. Cari URL untuk PTN nonaktif, nyalakan satu per satu, seed ulang otomatis.
9. Pasang cron-job.org: tiap 15 menit, POST ke `.../actions/workflows/run.yml/dispatches`, header `Authorization: Bearer <PAT>` + `Accept: application/vnd.github+json`, body `{"ref":"main"}`. PAT fine-grained, izin Actions write, hanya repo ini.
10. Pantau 3 hari. Setel: alarm palsu halaman (tambah `ignore_regex`), berita lolos tapi tidak relevan (tambah kata negatif), berita relevan tidak lolos (longgarkan kata).
11. Tes ujung ke ujung: kirim satu item uji (ubah halaman uji atau pakai `FORCE=1` dengan state dihapus pada satu sumber) dan pastikan masuk channel yang benar.

## 8. Risiko dan batas yang diketahui
- cron GitHub telat 5 sampai 60 menit. Jangan andalkan, pakai cron-job.org.
- Halaman JavaScript tidak terbaca (UPI, Kemendikdasmen). Perlu cari endpoint atau lewati.
- Situs yang membalas 200 untuk semua path bisa memicu `watch_appear` palsu (UGM v27).
- Item yang berubah teksnya kecil (typo fix) tetap terkirim sebagai "berubah".
- Disk state dibatasi 1500 id per feed, 4000 judul, 4000 hash per halaman.
- Rate limit Discord: ditangani retry, tapi lonjakan besar (mis. 15 berita sekaligus) lambat beberapa detik.
- Tidak ada ringkasan harian atau mingguan, tidak ada skor relevansi (sengaja, v1).
- Item "abu-abu" (hanya kata "sekolah" atau "siswa") tidak dikirim sama sekali. Rencana v2: digest harian.

## 9. Fakta domain untuk tuning keyword (per 11 Nov 2026)
- Situs SNPMB: snpmb.id. Jadwal SNPMB 2027 belum resmi. Perkiraan pengumuman Des 2026 (siklus 2026 diluncurkan 16 Sep 2025).
- Aturan tetap: lolos SNBP 2026 tidak boleh ikut SNBT dan mandiri 2026 sampai 2028.
- Pendaftaran mandiri KIP Kuliah sampai 11 Nov 2026.
- TKA SMA berlangsung akhir Okt sampai akhir Nov 2026.
- SPMB SMA lewat snt.kemendikdasmen.go.id/spmb.
- Topik kebijakan (RUU Sisdiknas, kuliah gratis Rp 93,7 T, LPDP) hanya tertangkap kata kunci luas.

## 10. Prompt awal untuk Claude Code baru (tempel apa adanya)
```
Baca HANDOFF.md dan README.md di repo ini. Proyek edu-radar sudah jadi dan lolos tes offline.
Tugas: selesaikan setup bagian 7 HANDOFF.md. Mulai dari langkah 1.
Aturan: jawab Bahasa Indonesia, ringkas, bullet, tanpa em dash, jangan pakai kata "Verdict".
Jangan ubah arsitektur. Jangan tambah LLM, DB, atau server.
Setelah run seed pertama, bacakan log, daftar sumber yang gagal, dan usul perbaikan sources.yml.
Tanya aku hanya untuk hal yang butuh akun atau secret (webhook, PAT, cron-job.org).
```

## 11. Isi paket
- `main.py`, `sources.yml`, `requirements.txt`, `state.json` (kosong, dibuat otomatis)
- `.github/workflows/run.yml`
- `README.md` (setup ringkas), `HANDOFF.md` (dokumen ini)
