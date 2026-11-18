"""Facilitated terminal interface for the local study."""

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import uuid
from pathlib import Path

from .session import Session
from .store import connect, initialize, verify


def multiline(prompt):
    while True:
        print(prompt + " Termine com uma linha contendo apenas .")
        lines = []
        while True:
            line = input()
            if line == ".":
                break
            lines.append(line)
        result = "\n".join(lines)
        print("\nPrévia:\n" + safe(result))
        if input("Gravar este texto? [s/N] ").strip().lower() == "s":
            return result


def safe(text):
    return "".join(c if (ord(c) >= 32 and not 127 <= ord(c) <= 159) or c in "\n\t"
                   else f"\\u{ord(c):04x}" for c in text)


def private_directory(path):
    if not path.is_dir():
        raise ValueError("Diretório privado não existe")
    if os.name != "nt":
        info = path.stat()
        if info.st_uid != os.geteuid() or info.st_mode & 0o077:
            raise ValueError("Diretório deve pertencer ao usuário e ter modo 0700")
        return
    script = """
$ErrorActionPreference = 'Stop'
$acl = [System.IO.Directory]::GetAccessControl($env:INTENTBRIDGE_ACL_CHECK)
$current = [System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$owner = ([System.Security.Principal.NTAccount]$acl.Owner).Translate(
    [System.Security.Principal.SecurityIdentifier]).Value
if ($owner -ne $current) { exit 2 }
$allowed = @($current, 'S-1-5-18', 'S-1-5-32-544', 'S-1-3-4')
foreach ($rule in $acl.GetAccessRules($true, $true, [System.Security.Principal.SecurityIdentifier])) {
    if ($rule.AccessControlType -eq 'Allow' -and $rule.IdentityReference.Value -notin $allowed) {
        exit 3
    }
}
"""
    environment = os.environ.copy()
    environment["INTENTBRIDGE_ACL_CHECK"] = str(path)
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
        env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        timeout=10, check=False,
    )
    if result.returncode:
        raise ValueError("ACL do diretório deve permitir somente o usuário, Administradores e Sistema")


def create_private_directory(path):
    if path.exists():
        private_directory(path)
        return
    path.mkdir(mode=0o700, parents=True)
    if os.name == "nt":
        script = """
$sid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
& icacls.exe $env:INTENTBRIDGE_ACL_CHECK /inheritance:r /grant:r ("*" + $sid + ":(OI)(CI)F") '*S-1-5-18:(OI)(CI)F' '*S-1-5-32-544:(OI)(CI)F'
exit $LASTEXITCODE
"""
        environment = os.environ.copy()
        environment["INTENTBRIDGE_ACL_CHECK"] = str(path)
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
            env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=10, check=False,
        )
        if result.returncode:
            raise ValueError("Não foi possível criar a ACL privada do diretório")
    private_directory(path)


def data_directory(value):
    selected = value or os.environ.get("INTENTBRIDGE_DATA_DIR")
    if not selected and os.environ.get("LOCALAPPDATA"):
        selected = str(Path(os.environ["LOCALAPPDATA"]) / "IntentBridge" / "study")
    if not selected:
        raise ValueError("Informe --data-dir ou INTENTBRIDGE_DATA_DIR")
    path = Path(selected)
    if not path.is_absolute():
        raise ValueError("Diretório de dados deve ser absoluto")
    path = path.resolve()
    project = Path(__file__).resolve().parent.parent
    if path == project or project in path.parents:
        raise ValueError("Diretório de dados deve ficar fora do repositório")
    if str(path).startswith("\\\\"):
        raise ValueError("Use um diretório local")
    return path


def destination(value):
    path = Path(value)
    if not path.is_absolute():
        raise ValueError("Destino deve ser absoluto")
    path = path.resolve()
    if not path.parent.is_dir():
        raise ValueError("Diretório de destino não existe")
    private_directory(path.parent)
    if path.exists():
        raise ValueError("Destino já existe")
    return path


def publish_file(path, writer):
    temporary = path.parent / ("." + str(uuid.uuid4()) + ".tmp")
    try:
        with temporary.open("xb") as file:
            writer(file)
            file.flush()
            os.fsync(file.fileno())
        os.link(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def session_path(directory, session_id):
    parsed = str(uuid.UUID(session_id))
    if parsed != session_id:
        raise ValueError("UUID de sessão inválido")
    path = directory / (parsed + ".sqlite3")
    if not path.is_file():
        raise ValueError("Sessão não encontrada")
    return path


def present(service):
    version = service.presented()
    print(f"\nVersão {version['revision']} · {version['id']}")
    print(version["content"].decode("utf-8"))
    if input("A pessoa examinou esta versão? [s/N] ").strip().lower() != "s":
        return None
    return service.record_presentation(version["id"], version["sha256"])


def choose(db, table, columns, condition="1=1"):
    rows = db.execute(f"SELECT {columns} FROM {table} WHERE {condition}").fetchall()
    for index, row in enumerate(rows, 1):
        print(index, " | ".join(safe(str(value)) for value in row))
    if not rows:
        raise ValueError("Nenhum registro disponível")
    index = int(input("Número: "))
    if index < 1 or index > len(rows):
        raise ValueError("Número inválido")
    return rows[index - 1][0]


def run_session(service):
    presentation = None
    try:
        while True:
            session = service.session()
            version = service.current()
            print(f"\nSessão {session['id']} · versão {version['revision']} · {session['status']}")
            print("1 Apresentar  2 Registrar resposta  3 Revisar  4 Propor checkpoint")
            print("5 Reconhecer  6 Reabrir  7 Histórico  8 Pausar  9 Encerrar")
            action = input("> ").strip()
            try:
                if action == "1":
                    presentation = present(service)
                elif action == "2":
                    if not presentation:
                        raise ValueError("Apresente a versão primeiro")
                    print("Pergunta sugerida: O que você mudaria nesta tela, se mudaria algo?")
                    kind = input("Tipo [feedback/rejection/reaction]: ").strip()
                    text = multiline("Transcreva as palavras da pessoa.")
                    print("Contribuição:", service.feedback(presentation, text, kind))
                elif action == "3":
                    contribution = choose(service.db, "contribution", "id,text",
                                          "version_id=(SELECT current_version FROM session)")
                    content = multiline("Digite o rascunho revisado com dados fictícios.")
                    summary = multiline("Descreva a mudança e sua relação com a contribuição.")
                    if input("Os dados do rascunho são fictícios? [s/N] ").lower() == "s":
                        service.revise(content, summary, contribution)
                        presentation = None
                elif action == "4":
                    if not presentation:
                        raise ValueError("Apresente a versão primeiro")
                    print("Pergunte antes: O que, se algo, esta versão resolveu ou ajudou você a entender?")
                    contribution = choose(service.db, "contribution", "id,text")
                    location = input("Seção ou linhas da evidência: ")
                    observation = multiline("Descreva a evidência observada.")
                    kind = input("Tipo [change/learning]: ").strip()
                    description = multiline("Descreva o candidato.")
                    predecessor = None
                    if input("Este candidato sucede um checkpoint reaberto? [s/N] ").lower() == "s":
                        predecessor = choose(service.db, "checkpoint", "id,description,status", "status='reopened'")
                    print("Checkpoint:", service.propose(presentation, contribution, location, observation,
                                                         kind, description, predecessor))
                elif action == "5":
                    if not presentation:
                        raise ValueError("Apresente a versão atual primeiro")
                    checkpoint = choose(service.db, "checkpoint", "id,description,status", "status='pending'")
                    row = service.row("SELECT c.description,e.location,e.observation,v.content FROM checkpoint c "
                                      "JOIN evidence e ON e.id=c.evidence_id JOIN version v ON v.id=c.version_id "
                                      "WHERE c.id=?", (checkpoint,))
                    print("\n" + row["content"].decode("utf-8"))
                    print("Evidência:", safe(row["location"]), safe(row["observation"]))
                    print("Candidato:", safe(row["description"]))
                    captured = service.retry_capture(checkpoint)
                    if captured:
                        print("Recibo:", service.confirm(checkpoint, captured["event_id"]))
                        continue
                    attempt = service.begin_attempt(checkpoint, presentation)
                    print("Pergunte: O que você quer registrar sobre esta versão?")
                    text = multiline("Transcreva a resposta da pessoa.")
                    print("Leia a resposta de volta e confirme a referência com a pessoa.")
                    specific = text.strip() and input(
                        "A fala reconhece especificamente este candidato e esta versão? [s/N] "
                    ).strip().lower() == "s"
                    if not specific:
                        if text.strip():
                            service.feedback(presentation, text, "reaction")
                        service.cancel_attempt(attempt, "Ambíguo, silêncio ou cancelamento")
                        print("Checkpoint pendente.")
                    else:
                        try:
                            event = service.capture(attempt, text)
                        except ValueError as error:
                            if str(error) != "Reconhecimento ambíguo permanece pendente":
                                raise
                            service.feedback(presentation, text, "reaction")
                            service.cancel_attempt(attempt, "Reconhecimento ambíguo")
                            print("Checkpoint pendente.")
                        else:
                            print("Recibo:", service.confirm(checkpoint, event))
                elif action == "6":
                    checkpoint = choose(service.db, "checkpoint", "id,description,status", "status='integrated'")
                    service.reopen(checkpoint, multiline("Registre o motivo da reabertura."))
                elif action == "7":
                    for row in service.db.execute("SELECT seq,kind,actor,text FROM event ORDER BY seq"):
                        print(" | ".join(safe(str(value)) for value in row))
                elif action in ("8", "9"):
                    service.change_status("paused" if action == "8" else "closed")
                    return
            except (ValueError, sqlite3.Error) as error:
                print("Operação não concluída:", error)
    except (EOFError, KeyboardInterrupt):
        print("\nSessão interrompida.")
        try:
            service.change_status("paused")
        except (ValueError, sqlite3.Error):
            print("Confira o último estado durável ao retomar.")


def main():
    parser = argparse.ArgumentParser(prog="intent_bridge")
    parser.add_argument("--data-dir")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check")
    commands.add_parser("study")
    for name in ("resume", "export", "backup"):
        command = commands.add_parser(name)
        command.add_argument("--session", required=True)
        if name in ("export", "backup"):
            command.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        directory = data_directory(args.data_dir)
        if args.command == "check":
            if sys.version_info < (3, 12):
                raise ValueError("Python 3.12 ou posterior é necessário")
            db = connect(":memory:")
            initialize(db)
            verify(db)
            db.close()
            parent = directory
            while not parent.exists() and parent != parent.parent:
                parent = parent.parent
            if not parent.is_dir() or not os.access(parent, os.W_OK):
                raise ValueError("Diretório de dados sem acesso de gravação")
            if directory.exists():
                private_directory(directory)
            print("Python e SQLite disponíveis. Diretório:", directory)
            return
        if args.command == "study":
            if not sys.stdin.isatty():
                raise ValueError("A sessão exige terminal interativo")
            request = multiline("Registre o pedido inicial.")
            print("Este estudo usa um rascunho provisório com dados fictícios.")
            if input("A pessoa aceita experimentar o primeiro rascunho? [s/N] ").lower() != "s":
                print("Sessão não iniciada.")
                return
            facilitator = input("Identificação do facilitador: ").strip()
            participant = input("Pseudônimo da pessoa: ").strip()
            create_private_directory(directory)
            session_id = str(uuid.uuid4())
            path = directory / (session_id + ".sqlite3")
            db = connect(path)
            try:
                initialize(db)
                service = Session(db)
                content = (Path(__file__).parent / "fixtures" / "v1.txt").read_text(encoding="utf-8")
                service.create(request, facilitator, participant, content, session_id)
            finally:
                db.close()
        else:
            private_directory(directory)
            path = session_path(directory, args.session)
        db = connect(path)
        try:
            verify(db)
            service = Session(db)
            if args.command != "study" and service.session()["id"] != args.session:
                raise ValueError("O identificador da sessão não corresponde ao arquivo")
            if args.command in ("study", "resume"):
                if not sys.stdin.isatty():
                    raise ValueError("A sessão exige terminal interativo")
                if args.command == "resume":
                    service.resume()
                run_session(service)
            elif args.command == "export":
                output = destination(args.output)
                db.execute("BEGIN")
                try:
                    records = {}
                    for table in ("session", "version", "event", "contribution", "version_contribution",
                                  "evidence", "checkpoint", "checkpoint_event", "attempt", "human_capture", "recognition"):
                        records[table] = [dict(row) for row in db.execute(f"SELECT * FROM {table}")]
                    for version in records["version"]:
                        version["content"] = version["content"].decode("utf-8")
                    payload = json.dumps({"schema_version": 2, "records": records}, ensure_ascii=False, indent=2)
                    json.loads(payload)
                    publish_file(output, lambda file: file.write(payload.encode("utf-8")))
                finally:
                    db.execute("ROLLBACK")
                print("Exportado:", output)
            else:
                output = destination(args.output)
                temporary = output.parent / ("." + str(uuid.uuid4()) + ".sqlite3")
                with temporary.open("xb"):
                    pass
                try:
                    target = connect(temporary)
                    try:
                        db.backup(target)
                        verify(target)
                    finally:
                        target.close()
                    os.link(temporary, output)
                finally:
                    if temporary.exists():
                        temporary.unlink()
                print("Backup:", output)
        finally:
            db.close()
    except (ValueError, OSError, sqlite3.Error, subprocess.SubprocessError) as error:
        print("Erro:", error, file=sys.stderr)
        raise SystemExit(1)
