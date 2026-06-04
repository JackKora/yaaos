import { setupServer } from "msw/node";

/**
 * Node.js MSW server for Vitest.
 *
 * Tests import `server` and call `server.use(...)` to override handlers
 * per-test. The global setup/teardown lives in `src/test-setup.ts`.
 */
export const server = setupServer();
