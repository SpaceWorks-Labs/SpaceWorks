---
title: Install Space Works
summary: Run the installer, answer its questions, and save what it prints at the end.
order: 10
keywords: install, installer, setup, server, first install, profile, https, storage, hosting, sudo
---
The installer sets up Space Works on a Linux server with Docker. Nothing changes on the server until you confirm the summary.

1. Run the one-line installer from the project's README as a user who can use `sudo`.
2. Choose the **Hosting** shape: one makerspace, several, or a hosted platform.
3. Choose whether this server serves the **Website** or only the API, how it gets **HTTPS** (plain, automatic, or your own proxy), and **Storage** (the bundled store or your own S3-compatible bucket).
4. Choose whether the control plane (`/control/`) is reachable from the web.
5. Answer the rest: your web address, organisation and first space, member two-step sign-in, sign-in providers, the areas your space runs, the admin login, and optional payments.
6. Read the summary and confirm.
7. Save the address and login the installer prints. Keep the generated `.env` file backed up somewhere safe, off the server.

![Screenshot: the installer summary before Proceed](screenshot:op-installer)

It installs into `/opt/spaceworks` unless you choose another folder. The default profile runs every background job on the server; a free-tier profile is a separate opt-in.

> **Who can do this:** the host operator, with administrator access to the server.
