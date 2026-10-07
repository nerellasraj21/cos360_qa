// Auth F08 Token refresh and expiry, web. All cases are blocked by the known 400-instead-of-401 gap.
const { test } = require('../../helpers/fixtures');

const REASON = 'blocked: an invalid bearer token sent without a cschema header gets 400, not 401, so the web refresh never runs (docs/modules/auth.md Known gaps)';

test.describe('Auth F08 token refresh (web)', () => {
  test('TC-AUTH-08-E01 invalid access token is refreshed', async () => {
    test.skip(true, REASON);
  });

  test('TC-AUTH-08-E02 invalid access and refresh tokens end the session', async () => {
    test.skip(true, REASON);
  });

  test('TC-AUTH-08-E03 concurrent failures share one refresh', async () => {
    test.skip(true, REASON);
  });
});
