#!/usr/bin/env python3
"""Build both same-signed Leanback variants and the HOME API helper locally."""
import argparse
import os
import secrets
import subprocess
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--sdk", type=Path, required=True)
    p.add_argument("--java-home", type=Path, required=True)
    p.add_argument("--build-tools", default="34.0.0")
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    scripts = Path(__file__).resolve().parent
    output = a.output.resolve()
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    java = a.java_home.resolve()
    tools = a.sdk.resolve() / "build-tools" / a.build_tools
    android = a.sdk.resolve() / "platforms/android-25/android.jar"
    env = dict(os.environ, JAVA_HOME=str(java))
    def run(*cmd):
        subprocess.run(list(map(str, cmd)), check=True, env=env)
    password = output / "signing-password.txt"
    password.write_text(secrets.token_urlsafe(32))
    password.chmod(0o600)
    key = output / "launcher-local.jks"
    run(java / "bin/keytool", "-genkeypair", "-keystore", key,
        "-storepass:file", password, "-keypass:file", password,
        "-alias", "launcher-local", "-keyalg", "RSA", "-keysize", "3072",
        "-validity", "3650", "-dname", "CN=Local TV Launcher")
    key.chmod(0o600)
    for mode in ("app", "home"):
        unsigned = output / (mode + "-unsigned.apk")
        aligned = output / (mode + "-aligned.apk")
        apk = output / ("leanback-" + mode + "-local.apk")
        run(os.sys.executable, scripts / ("make_" + mode + "_apk.py"),
            "--source", a.source.resolve(), "--output", unsigned)
        run(tools / "zipalign", "-f", "4", unsigned, aligned)
        run(tools / "apksigner", "sign", "--ks", key, "--ks-key-alias", "launcher-local",
            "--ks-pass", "file:" + str(password), "--out", apk, aligned)
        run(tools / "apksigner", "verify", "--verbose", "--print-certs", apk)
    classes, dex = output / "classes", output / "dex"
    classes.mkdir(); dex.mkdir()
    run(java / "bin/javac", "-source", "8", "-target", "8", "-classpath", android,
        "-d", classes, scripts / "HomePreference.java")
    run(tools / "d8", "--min-api", "22", "--lib", android, "--output", dex,
        classes / "HomePreference.class")
    run(java / "bin/jar", "cf", output / "home-preference.jar", "-C", dex, "classes.dex")
    print("Keep this directory and its signing key privately. No device was changed.")


if __name__ == "__main__":
    main()
