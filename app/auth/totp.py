import base64
import io
import pyotp
import qrcode

def generate_totp_secret() -> str:
    return pyotp.random_base32()

def get_provisioning_uri(username: str, secret: str, issuer_name: str = "SyncTool") -> str:
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=username, issuer_name=issuer_name)

def generate_qr_code_base64(provisioning_uri: str) -> str:
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=8,
        border=3,
    )
    qr.add_data(provisioning_uri)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{img_str}"

def verify_totp_code(secret: str, code: str) -> bool:
    if not secret or not code:
        return False
    totp = pyotp.TOTP(secret)
    # valid_window=1 allows 30 seconds clock drift leeway
    return totp.verify(code.strip(), valid_window=1)
