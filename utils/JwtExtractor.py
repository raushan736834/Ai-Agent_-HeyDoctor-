from jose import jwt

def extract_user_id_from_jwt(jwt_token:str) -> str:
    try:
        payload = jwt.get_unverified_claims(jwt_token)
        return payload.get("sub") or payload.get('email')
    except Exception:
        return 'anonymouse'