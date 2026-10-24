"""Run manually in a local browser; submit test text, never a real key."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from private_input import serve


def discard(value):
    return None


if __name__ == "__main__":
    serve(discard, purpose="仅测试输入流程：内容将丢弃，请勿输入真实密钥。")
