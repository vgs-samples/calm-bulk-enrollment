import csv
import json
import os
from pathlib import Path

import requests
import jwt

jwt_cached = None


def request_data(name, number, exp_month, exp_year):
    return {
        "name": name,
        "number": number,
        "exp_month": int(exp_month),
        "exp_year": int(exp_year),
        "capabilities": [
            "ACCOUNT_UPDATER"
        ]
    }


def provide_jwt():
    global jwt_cached
    if not is_jwt_valid(jwt_cached):
        jwt_cached = fetch_jwt()
    return jwt_cached


def is_jwt_valid(token):
    if token is None:
        return False
    try:
        jwt.decode(token, 'secret', algorithms='RS256',
                   options={'verify_signature': False, 'verify_aud': False})
    except (jwt.DecodeError, jwt.ExpiredSignatureError):
        return False
    return True


def fetch_jwt():
    token_url = 'https://auth.verygoodsecurity.com/auth/realms/vgs/protocol/openid-connect/token'

    payload = {
        'client_id': f'{calm_client_id}',
        'client_secret': f'{calm_client_secret}',
        'grant_type': 'client_credentials'
    }
    response = requests.post(token_url, data=payload)
    return response.json()['access_token']


def alias_raw_data():
    print(f'Starting aliasing of raw data from file "csv/card_numbers.csv" in vault {vault_id}.')
    with open('csv/card_numbers.csv') as raw_cards_file:
        with open('csv/aliased_cards.csv', 'w') as aliased_cards_file:
            cards = csv.reader(raw_cards_file)
            next(cards)
            header = ['Name', 'CardNumber', 'ExpirationMonth', 'ExpirationYear']
            aliased = csv.writer(aliased_cards_file)
            aliased.writerow(header)
            for card in cards:
                card_number = card[1]
                print(f'Aliasing card number {card_number[6:]}******{card_number[:4]}')
                r = requests.post(f'https://{vault_id}.{environment}.verygoodproxy.com/post',
                                  json={'account_number': card_number}
                                  )
                alias = json.loads(r.json()['data'])['account_number']
                aliased.writerow([card[0], alias, card[2], card[3]])
    print(f'Successfully aliased raw data in vault {vault_id}. See "csv/aliased_cards.csv" for created aliases.')


def enroll_data(aliased=False):
    file_name = "csv/aliased_cards.csv" if aliased else "csv/card_numbers.csv"

    print(f'Starting one-time enrollment process from file "{file_name}".')
    with open(f'{file_name}') as cards_file:
        with open('csv/updated_cards.csv', 'w') as updated_cards_file:
            cards = csv.reader(cards_file)
            next(cards)
            header = ['Id', 'Name', 'CardNumber', 'ExpirationMonth', 'ExpirationYear']
            updated = csv.writer(updated_cards_file)
            updated.writerow(header)
            for card in cards:
                card_number = card[1]
                print(f'Enrolling card number {card_number[6:]}******{card_number[:4]}')
                proxies = {
                    'https': f'https://{vault_username}:{vault_password}@{vault_id}.{environment}.verygoodproxy.com:8080'}
                r = requests.post(f'https://calm.{environment}.verygoodsecurity.app/cards',
                                  json=request_data(card[0], card_number, card[2], card[3]),
                                  headers={
                                      'Content-Type': 'application/json',
                                      'Authorization': f'Bearer {fetch_jwt()}'
                                  },
                                  proxies=proxies if aliased else None,
                                  verify=Path(__file__).resolve().parent / f'certs/{environment}_cert.pem' if aliased else None
                                  )
                data = r.json()['data']
                card_id = data['id']
                name = data['name']
                updated_number = data['number']
                updated_exp_month = data['exp_month']
                updated_exp_year = data['exp_year']
                updated.writerow([card_id, name, updated_number, updated_exp_month, updated_exp_year])
    print(
        f'Successfully finish one-time enrollment process. '
        f'See "csv/updated_cards.csv" for enrolled card with their corresponding ID\'s.')


if __name__ == "__main__":
    vault_id = os.getenv('VAULT_ID')
    vault_username = os.getenv('VAULT_USERNAME')
    vault_password = os.getenv('VAULT_PASSWORD')
    environment = os.getenv('ENVIRONMENT', 'sandbox')
    calm_client_id = os.getenv('CALM_CLIENT_ID')
    calm_client_secret = os.getenv('CALM_CLIENT_SECRET')
    alias_cards = os.getenv('ALIAS_CARDS')
    enroll_aliases = os.getenv('ENROLL_ALIASES')

    if not vault_id and (alias_cards or enroll_aliases):
        print('Required VAULT_ID variable is missing.')
        exit(1)

    if alias_cards == "true":
        alias_raw_data()
    elif enroll_aliases == "true":
        if not vault_username and not vault_password:
            print('Required VAULT_USERNAME and VAULT_PASSWORD variables are missing.')
            exit(1)

        if not calm_client_id and not calm_client_secret:
            print('Required CALM_CLIENT_ID and CALM_CLIENT_SECRET variables are missing.')
            exit(1)

        enroll_data(aliased=True)
    else:
        enroll_data(aliased=False)
