/* Diagnostic object using the unchanged, selected KOS allocator source.
 * Its existing MALLOC_DEBUG consistency assertions catch corruption earlier
 * than a later unlink. The shared SDK/library is never changed.
 */
#define MALLOC_DEBUG 1
#define __assert re4dc_heap_assert
#define __assert_func re4dc_heap_assert_func
#include "malloc.c"

#include <arch/irq.h>
#include <kos/thread.h>

extern void re4dc_log(const char*, ...);
extern void re4dc_halt(const char*, int) __attribute__((noreturn));
extern unsigned re4dc_ui_frame(void);

/* Fixed storage only. The sequence is reserved before entering malloc, so
 * an assertion/fault retains the caller of the unfinished operation. */
struct heap_event {
    unsigned sequence, op, pointer, bytes, caller, frame, tid, done;
};
static struct heap_event heap_events[16];
static unsigned heap_sequence;

static unsigned note(unsigned op, const void* ptr, size_t bytes, const void* caller) {
    const int old = irq_disable();
    const unsigned sequence = ++heap_sequence;
    struct heap_event* e = &heap_events[sequence % 16];
    e->sequence = sequence; e->op = op; e->pointer = (uintptr_t)ptr;
    e->bytes = bytes; e->caller = (uintptr_t)caller;
    e->frame = re4dc_ui_frame(); e->tid = thd_current ? thd_current->tid : 0;
    e->done = 0;
    irq_restore(old);
    return sequence;
}
static void done(unsigned sequence, const void* ptr) {
    const int old = irq_disable();
    struct heap_event* e = &heap_events[sequence % 16];
    if (e->sequence == sequence) { e->pointer = (uintptr_t)ptr; e->done = 1; }
    irq_restore(old);
}

/* Callable at a frame boundary. KOS owns the mutex and invariant definitions;
 * no second allocator or replacement ownership rules are introduced. */
void re4dc_heap_check(void) {
    if (MALLOC_PREACTION != 0) return;
    check_malloc_state();
    (void)MALLOC_POSTACTION;
}

int re4dc_heap_event_line(unsigned age, char* out, unsigned size) {
    if (!size || age >= 16 || age >= heap_sequence) return 0;
    const struct heap_event* e = &heap_events[(heap_sequence - age) % 16];
    snprintf(out, size, "H%c%s t%u p%08x n%u pc%06x f%u", (int)e->op,
             e->done ? "+" : "?", e->tid, e->pointer, e->bytes,
             e->caller & 0xffffffU, e->frame);
    return 1;
}

void re4dc_heap_assert(const char* file, int line, const char* expr,
                       const char* msg, const char* func) {
    (void)msg;
    re4dc_log("HEAP CHECK %s:%d %s: %s\n", file, line, func, expr);
    for (unsigned i = 0; i < 16 && i < heap_sequence; ++i) {
        char text[96];
        if (re4dc_heap_event_line(i, text, sizeof(text))) re4dc_log("%s\n", text);
    }
    re4dc_halt("KOS heap check", line);
}
void re4dc_heap_assert_func(const char* file, int line, const char* func, const char* expr) {
    re4dc_heap_assert(file, line, expr, 0, func);
}

extern void* __real_malloc(size_t);
extern void* __real_calloc(size_t, size_t);
extern void* __real_realloc(void*, size_t);
extern void* __real_memalign(size_t, size_t);
extern void __real_free(void*);
void* __wrap_malloc(size_t n) {
    unsigned s = note('M', 0, n, __builtin_return_address(0));
    void* p = __real_malloc(n); done(s, p); return p;
}
void* __wrap_calloc(size_t n, size_t z) {
    unsigned s = note('C', 0, z && n > SIZE_MAX / z ? SIZE_MAX : n * z, __builtin_return_address(0));
    void* p = __real_calloc(n, z); done(s, p); return p;
}
void* __wrap_realloc(void* p, size_t n) {
    unsigned s = note('R', p, n, __builtin_return_address(0));
    void* q = __real_realloc(p, n); done(s, q); return q;
}
void* __wrap_memalign(size_t a, size_t n) {
    unsigned s = note('A', 0, n, __builtin_return_address(0));
    void* p = __real_memalign(a, n); done(s, p); return p;
}
void __wrap_free(void* p) {
    unsigned s = note('F', p, 0, __builtin_return_address(0));
    __real_free(p); done(s, p);
}
#undef __assert
#undef __assert_func
