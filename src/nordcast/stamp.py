"""Independent proof that a frozen call existed before the release.

The repo is private and git commit times can be set to anything, so each
frozen file is also stamped with OpenTimestamps (https://opentimestamps.org).
The public calendars take the file's hash at once and anchor it in a Bitcoin
block within a few hours. The .ots proof next to the file lets anyone check
that, without trusting this project, GitHub or the calendars.

Stamping never blocks a freeze: if the calendars can't be reached, the freeze
is committed without a proof and the failure is printed.
"""

import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import httpx
from opentimestamps.core.notary import BitcoinBlockHeaderAttestation
from opentimestamps.core.op import OpSHA256
from opentimestamps.core.serialize import StreamDeserializationContext
from opentimestamps.core.timestamp import DetachedTimestampFile

OTS = str(Path(sys.executable).with_name("ots"))
BLOCKS = "https://blockstream.info/api"


def proof_path(path):
    return Path(f"{path}.ots")


def stamp(path, run=subprocess.run):
    """Submit the file to the calendars. Returns the .ots path, or None."""
    try:
        run([OTS, "stamp", str(path)], check=True, capture_output=True, timeout=90)
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"timestamp skipped: {type(exc).__name__}; the freeze still stands")
        return None
    return proof_path(path)


def read(ots_path):
    with open(ots_path, "rb") as fd:
        return DetachedTimestampFile.deserialize(StreamDeserializationContext(fd))


def bitcoin_heights(ots_path):
    """[(block height, merkle root the proof commits to)], empty while pending."""
    return [
        (att.height, msg)
        for msg, att in read(ots_path).timestamp.all_attestations()
        if isinstance(att, BitcoinBlockHeaderAttestation)
    ]


def is_complete(ots_path):
    return bool(bitcoin_heights(ots_path))


def upgrade(ots_path, run=subprocess.run):
    """Fetch the Bitcoin attestation from the calendars once it exists.
    Returns True if the proof is complete afterwards."""
    if is_complete(ots_path):
        return True
    try:
        run([OTS, "upgrade", str(ots_path)], capture_output=True, timeout=90)
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"upgrade skipped for {Path(ots_path).name}: {type(exc).__name__}")
        return False
    return is_complete(ots_path)


def block_time(height, merkle_root, client):
    """The block's time if its merkle root matches the proof, else None."""
    block_hash = client.get(f"{BLOCKS}/block-height/{height}").text.strip()
    block = client.get(f"{BLOCKS}/block/{block_hash}").json()
    # The explorer shows the root byte-reversed, as Bitcoin displays hashes.
    if bytes.fromhex(block["merkle_root"])[::-1] != merkle_root:
        return None
    return datetime.fromtimestamp(block["timestamp"], UTC)


def check(path, client=None):
    """What the proof shows about the file at `path`.

    Returns ('missing' | 'mismatch' | 'pending' | 'bad_block' | 'anchored',
    block time or None). 'anchored' means the file existed by that time.
    """
    ots_path = proof_path(path)
    if not ots_path.exists():
        return "missing", None
    proof = read(ots_path)
    with open(path, "rb") as fd:
        digest = DetachedTimestampFile.from_fd(OpSHA256(), fd).file_digest
    if digest != proof.file_digest:
        return "mismatch", None
    heights = bitcoin_heights(ots_path)
    if not heights:
        return "pending", None
    client = client or httpx.Client(timeout=20)
    times = [block_time(h, root, client) for h, root in heights]
    good = [t for t in times if t is not None]
    return ("anchored", min(good)) if good else ("bad_block", None)
