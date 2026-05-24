package backoff

import (
	"context"
	"testing"
	"time"
)

func TestSchedule_HitsExpectedSteps(t *testing.T) {
	// With jitter forced to 0, Peek() returns each step in order, then
	// pins at the last step forever.
	s := newWithRNG(zeroJitter)
	want := []time.Duration{
		1 * time.Minute, 3 * time.Minute, 5 * time.Minute,
		15 * time.Minute, 60 * time.Minute,
	}
	for i, w := range want {
		got := s.Peek()
		if got != w {
			t.Fatalf("attempt %d: want %s, got %s", i, w, got)
		}
		s.advance() // simulate Sleep without actually sleeping
	}
	// Beyond the last step the schedule pins at 60m.
	for i := 0; i < 5; i++ {
		if got := s.Peek(); got != 60*time.Minute {
			t.Fatalf("post-cap attempt %d: want 60m, got %s", i, got)
		}
		s.advance()
	}
}

func TestSchedule_JitterWithinBand(t *testing.T) {
	// 1000 samples per attempt — every one must fall inside [0.8x, 1.2x].
	s := New()
	base := []time.Duration{
		1 * time.Minute, 3 * time.Minute, 5 * time.Minute,
		15 * time.Minute, 60 * time.Minute,
	}
	for attempt, b := range base {
		lo := time.Duration(float64(b) * 0.8)
		hi := time.Duration(float64(b) * 1.2)
		for i := 0; i < 1000; i++ {
			d := s.windowedFor(attempt)
			if d < lo || d > hi {
				t.Fatalf("attempt %d sample %d: %s outside [%s,%s]",
					attempt, i, d, lo, hi)
			}
		}
	}
}

func TestSchedule_ResetReturnsToZero(t *testing.T) {
	s := newWithRNG(zeroJitter)
	s.advance()
	s.advance()
	s.advance()
	if got := s.Peek(); got != 15*time.Minute {
		t.Fatalf("pre-reset: want 15m, got %s", got)
	}
	s.Reset()
	if got := s.Peek(); got != 1*time.Minute {
		t.Fatalf("post-reset: want 1m, got %s", got)
	}
}

func TestSchedule_SleepRespectsContextCancel(t *testing.T) {
	// Sleep returns ctx.Err() immediately on cancel — operator's
	// SIGTERM during a long backoff shouldn't wait minutes to exit.
	s := New()
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	start := time.Now()
	if err := s.Sleep(ctx); err != context.Canceled {
		t.Fatalf("want context.Canceled, got %v", err)
	}
	if time.Since(start) > 100*time.Millisecond {
		t.Fatalf("Sleep blocked despite cancel")
	}
}

// zeroJitter forces windowed() to return exactly the base step (no
// random component). Used for deterministic step-progression tests.
func zeroJitter() float64 { return 0.5 } // (0.5*2 - 1) * 0.2 == 0
