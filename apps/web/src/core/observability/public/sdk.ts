/**
 * OpenTelemetry SDK initialization for the yaaos SPA.
 *
 * Call configure() once at boot (main.tsx) before rendering.
 * Export is gated on the collector endpoint: endpoint present → export via
 * OTLP/HTTP; endpoint absent → SDK still creates spans but does not export.
 * No feature flag needed — the gating condition is the endpoint itself.
 *
 * Instrumentations registered:
 * - FetchInstrumentation: injects traceparent ONLY on same-origin /api/
 *   requests (propagateTraceHeaderCorsUrls anchored to window.location.origin).
 *   Cross-origin fetches (collector, CDN, third-party) never receive traceparent.
 * - DocumentLoadInstrumentation: captures page-load performance entries.
 * - UserInteractionInstrumentation: wraps click/submit handlers with spans.
 *
 * Identity: SpanProcessor.onStart stamps yaaos.org_id / yaaos.user_id from
 * the module-scope identity holder (see identity.ts). Call setIdentity()
 * after auth resolves. No baggage header is ever emitted.
 */

import { SpanStatusCode, trace } from "@opentelemetry/api";
import { OTLPTraceExporter } from "@opentelemetry/exporter-trace-otlp-http";
import { registerInstrumentations } from "@opentelemetry/instrumentation";
import { DocumentLoadInstrumentation } from "@opentelemetry/instrumentation-document-load";
import { FetchInstrumentation } from "@opentelemetry/instrumentation-fetch";
import { UserInteractionInstrumentation } from "@opentelemetry/instrumentation-user-interaction";
import { resourceFromAttributes } from "@opentelemetry/resources";
import {
  BatchSpanProcessor,
  NoopSpanProcessor,
  WebTracerProvider,
} from "@opentelemetry/sdk-trace-web";
import { ATTR_SERVICE_NAME } from "@opentelemetry/semantic-conventions";
import { _resetIdentityForTests } from "../identity";
import { YaaosSpanProcessor } from "../span-processor";

export { setIdentity } from "../identity";
export { YaaosSpanProcessor } from "../span-processor";

export interface ObservabilityConfig {
  collectorEndpoint: string | undefined;
}

let _provider: WebTracerProvider | null = null;

/**
 * Initialize the OTel SDK. Safe to call multiple times (subsequent calls are
 * no-ops once initialized, unless _resetObservabilityForTests() was called).
 */
export function configure(config: ObservabilityConfig): void {
  if (_provider !== null) return;

  const resource = resourceFromAttributes({
    [ATTR_SERVICE_NAME]: "yaaos-web",
  });

  // Build the span processor pipeline. YaaosSpanProcessor stamps yaaos.*
  // identity attributes on every web-originating span.
  const spanProcessors = config.collectorEndpoint
    ? [
        new YaaosSpanProcessor(),
        // Batch export to the OTLP collector. Spans are batched to minimize request overhead.
        new BatchSpanProcessor(
          new OTLPTraceExporter({ url: `${config.collectorEndpoint}/v1/traces` }),
        ),
      ]
    : [
        new YaaosSpanProcessor(),
        // No collector endpoint — SDK is active (spans created, traceparent injected)
        // but no data leaves the browser. Instrumentation still generates trace context
        // so the backend gets a valid parent span.
        new NoopSpanProcessor(),
      ];

  _provider = new WebTracerProvider({ resource, spanProcessors });
  _provider.register();

  // Register auto-instrumentations after provider is registered.
  // propagateTraceHeaderCorsUrls restricts traceparent to same-origin /api/
  // requests. FetchInstrumentation matches against the resolved request URL
  // (absolute), so we anchor to window.location.origin to correctly exclude
  // cross-origin fetches where the path alone could match coincidentally.
  const apiOriginPattern = new RegExp(`^${window.location.origin}/api/`);
  registerInstrumentations({
    instrumentations: [
      new DocumentLoadInstrumentation(),
      new FetchInstrumentation({
        clearTimingResources: true,
        propagateTraceHeaderCorsUrls: [apiOriginPattern],
      }),
      new UserInteractionInstrumentation(),
    ],
  });

  // Install global error capture. Uncaught errors attach to the active span
  // (typically a user-interaction span) or to a short-lived span if none is
  // active.
  _installGlobalErrorHandlers();
}

/**
 * Record an exception on the currently active span (or on a short-lived
 * fallback span if no span is active). Sets span status to ERROR.
 */
export function recordException(err: unknown): void {
  const errObj = err instanceof Error ? err : new Error(String(err));
  const activeSpan = trace.getActiveSpan();
  if (activeSpan?.isRecording()) {
    activeSpan.recordException(errObj);
    activeSpan.setStatus({ code: SpanStatusCode.ERROR, message: String(err) });
    return;
  }

  // No active span — open a short-lived span to carry the exception event.
  const tracer = trace.getTracer("yaaos-web");
  tracer.startActiveSpan("client.unhandled_error", (span) => {
    span.recordException(errObj);
    span.setStatus({ code: SpanStatusCode.ERROR, message: String(err) });
    span.end();
  });
}

// Stable handler references kept in module scope so _resetObservabilityForTests
// can removeEventListener the exact same function objects.
let _onErrorHandler: ((event: ErrorEvent) => void) | null = null;
let _onUnhandledHandler: ((event: PromiseRejectionEvent) => void) | null = null;

function _installGlobalErrorHandlers(): void {
  // Use addEventListener so we compose with pre-existing handlers rather than
  // replacing them. removeEventListener in _resetObservabilityForTests restores
  // the prior state exactly — no prev* capture needed.
  _onErrorHandler = (event: ErrorEvent): void => {
    recordException(event.error ?? new Error(event.message));
  };
  _onUnhandledHandler = (event: PromiseRejectionEvent): void => {
    recordException(event.reason instanceof Error ? event.reason : new Error(String(event.reason)));
  };
  window.addEventListener("error", _onErrorHandler);
  window.addEventListener("unhandledrejection", _onUnhandledHandler);
}

/**
 * Reset SDK state for tests. Clears the provider so configure() can be
 * called again in each test. Also resets the identity holder.
 */
export function _resetObservabilityForTests(): void {
  if (_provider) {
    void _provider.shutdown().catch(() => {
      // Ignore shutdown errors in tests
    });
    _provider = null;
  }
  // Remove only the handlers we installed — prior handlers are untouched.
  if (_onErrorHandler) {
    window.removeEventListener("error", _onErrorHandler);
    _onErrorHandler = null;
  }
  if (_onUnhandledHandler) {
    window.removeEventListener("unhandledrejection", _onUnhandledHandler);
    _onUnhandledHandler = null;
  }
  _resetIdentityForTests();
}
