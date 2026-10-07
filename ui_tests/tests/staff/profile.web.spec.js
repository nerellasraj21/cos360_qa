// Staff F12 staff self-service profile (web).
const { test } = require('../../helpers/fixtures');

test.describe('Staff profile (web)', () => {
  test('TC-STF-12-E01 staff opens the Staff Profile', async () => {
    test.skip(true, 'blocked: qa_manual grants no profile:read_own or profile:update_own to Admin, Staff or Teacher (default seed), so /profile/staff/me answers 403 and the page falls back to My Profile');
  });
});
