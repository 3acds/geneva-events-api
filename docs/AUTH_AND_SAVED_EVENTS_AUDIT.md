# Authentication and saved-events audit

## Existing state

- The frontend used Firebase Authentication with Google popup sign-in.
- No passwords were collected or stored by this project; Google/Firebase owns credential handling.
- React authentication state was memory-only and disappeared on refresh.
- Logout cleared React state without signing out of Firebase.
- The profile page was conditionally rendered but was not a protected route.
- Browser code wrote profile records directly to Firebase Realtime Database.
- The Flask API had an abandoned, commented JWT example with placeholder credentials; it was never registered.
- No backend endpoint verified Firebase identity.

## Implemented foundation

Firebase remains the identity provider. Protected API routes verify Firebase ID
tokens, including revocation, through the Admin SDK. Authentication failures are
generic, and saved-event ownership comes exclusively from the verified token UID.

Saves use `users/{uid}/saved_events/{event_id}` in Firestore with `event_id` and
`saved_at`. The event ID document key makes saves idempotent. Event data is
resolved at read time, so deleted events are returned as unavailable.

## Remaining risks

- Realtime Database rules for legacy profile writes are outside this repository and require separate review.
- Revocation checks add an authentication-service lookup to protected calls.
- There are no organiser, submission, or moderation permissions.
