"""Verify the OpenAI text path returns the right dict shape before building images on it."""
from core.attacker import send_payload
from dotenv import load_dotenv
load_dotenv()
MODEL = "gpt-4o-mini"

from tests.llm01_img import LLM01ImgTest
t = LLM01ImgTest()
p = t.load_payloads()[0]
for m in ["claude-haiku-4-5-20251001", "gpt-4o-mini"]:
    o = t.send(m, p)
    print(m, "->", t.evaluate(p, o)["verdict"])


