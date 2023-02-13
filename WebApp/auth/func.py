from flask_login import UserMixin
import random
import string


class User(UserMixin):
    pass

def id_generator(size=6, chars=string.ascii_lowercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))
def is_legal_rate(rate):
    try:
        float(rate)
        if float(rate) <= 1 and float(rate) >= 0:
            return True
        else:
            return False
    except ValueError:
        return False
def is_legal_password(password):
    # define a legal pw
    # 1. contains 1 uppercase letter and 1 lowercase letter
    # 2. contains 1 digit
    # 3. at least have length of 8

    if len(password) < 8:
        return False

    check_1 = False
    check_2 = False
    check_3 = False
    for char in password:
        if char.isupper():
            check_1 = True
        if char.islower():
            check_2 = True
        if char.isdigit():
            check_3 = True

    if check_1 and check_2 and check_3:
        return True
    else:
        return False 