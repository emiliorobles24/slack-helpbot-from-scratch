# Password reset and account lockout (Okta)

All company logins go through Okta single sign-on. Password problems and lockouts are self-service in almost every case.

## Reset a forgotten password

Go to the Okta sign-in page and choose "Forgot password". Verification arrives through your enrolled MFA factor (push notification or SMS to your enrolled phone). Passwords must be at least 12 characters and cannot match your previous 8 passwords. The reset takes effect everywhere within about a minute; you do not need to change it in each app.

## Locked out after failed attempts

Accounts lock automatically after 10 consecutive failed attempts and unlock on their own after 15 minutes. If you cannot wait, use "Unlock account" on the Okta sign-in page, which verifies you through your MFA factor. Repeated lockouts you did not cause can indicate someone else trying your account: report that to IT immediately rather than just unlocking.

## If you suspect your account is compromised

Do not just reset the password. Contact IT through the help desk urgent line first so sessions can be revoked everywhere, then reset. Signs include MFA prompts you did not trigger, login notification emails from unfamiliar locations, and lockouts you did not cause.
