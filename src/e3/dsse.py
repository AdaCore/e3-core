from __future__ import annotations
from e3.os.process import Run
import base64
import json
import tempfile
import os


class DSSEError(Exception):
    pass


class DSSE:
    """DSSE: Dead Simple Signing Envelope.

    The current implementation relies on openssl tool.
    """

    def __init__(self, body: str | bytes, payload_type: str) -> None:
        """Initiazse a DSSE envelope.

        :param body: the content to sign
        :param payload_type: the type of the payload
        """
        if isinstance(body, str):
            self.body = body.encode("utf-8")
        else:
            self.body = body
        self.payload_type = payload_type
        self.signatures: list[dict[str, str]] = []

    def sign(self, key_id: str, private_key: str) -> str:
        """Sign the payload using openssl X509 certificate.

        :param key_id: the key id (used by end-user to identify which key to use
            for verification).
        :param private_key: path to file containing the private key
        :return: return the signature as base64 string
        """
        p = Run(
            ["openssl", "dgst", "-sha256", "-sign", private_key, "-out", "-", "-"],
            input=b"|" + self.pae,
        )
        if p.status == 0 and p.raw_out is not None:
            base64_signature = base64.b64encode(p.raw_out).decode("utf-8")
            self.signatures.append({"keyid": key_id, "sig": base64_signature})
            return base64_signature
        else:
            raise DSSEError(f"SSL error: {p.out}")

    def verify(self, certificate: str) -> bool:
        """Preliminary check on the signature.

        The current algorithm is to check that at least one signature correspond
        to the certificate given as parameter. This part should be improved

        :param certificate: path to the certificate containing the public key
        :return: True if one of the signature can be checked with the certificate
        """
        # First get the public key
        p = Run(["openssl", "x509", "-pubkey", "-noout", "-in", certificate])
        if p.status != 0 or p.raw_out is None:
            raise DSSEError(f"Cannot fetch public key from {certificate}")
        public_key = p.raw_out

        with tempfile.TemporaryDirectory() as temp_dir:
            with open(os.path.join(temp_dir, "pub.crt"), "wb") as fd:
                fd.write(public_key)

            with open(os.path.join(temp_dir, "pae"), "wb") as fd:
                fd.write(self.pae)

            for s in self.signatures:
                with open(os.path.join(temp_dir, "sig"), "wb") as fd:
                    fd.write(base64.b64decode(s["sig"]))

                p = Run(
                    [
                        "openssl",
                        "dgst",
                        "-verify",
                        os.path.join(temp_dir, "pub.crt"),
                        "-signature",
                        os.path.join(temp_dir, "sig"),
                        os.path.join(temp_dir, "pae"),
                    ],
                )
                if p.status == 0:
                    return True
            return False

    @property
    def payload(self) -> str:
        """Return the content to sign as base64 string.

        :return: a base64 string representing the content
        """
        return base64.b64encode(self.body).decode("utf-8")

    @property
    def pae(self) -> bytes:
        """Return the Pre-Authentication Encoding.

        This is the content that is really signed
        """
        payload_type_bytes = self.payload_type.encode("utf-8")
        return b" ".join(
            (
                b"DSSEv1",
                str(len(payload_type_bytes)).encode("utf-8"),
                payload_type_bytes,
                str(len(self.body)).encode("utf-8"),
                self.body,
            )
        )

    def as_dict(self) -> dict:
        """Return the dict representing the DSSE envelope."""
        return {
            "payload": self.payload,
            "payloadType": self.payload_type,
            "signatures": self.signatures,
        }

    def as_json(self) -> str:
        """Return the DSSE envelope."""
        return json.dumps(self.as_dict())

    @classmethod
    def load_json(cls, envelope: str) -> DSSE:
        """Load a json DSSE string and return a Python DSSE object.

        :param envelope: the json envelope
        """
        return cls.load_dict(json.loads(envelope))

    @classmethod
    def load_dict(cls, envelope: dict) -> DSSE:
        """Load a dict and return a Python DSSE object.

        :param envelope: the json envelope
        """
        result = cls(
            body=base64.b64decode(envelope["payload"]),
            payload_type=envelope["payloadType"],
        )
        result.signatures = [
            {"keyid": sig["keyid"], "sig": sig["sig"]} for sig in envelope["signatures"]
        ]
        return result
