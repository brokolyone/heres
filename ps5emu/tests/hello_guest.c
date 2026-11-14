// A tiny freestanding "game" used to test the emulator end to end.
// Imports are declared with their NID-encoded names ("NID#lib#module"),
// exactly like symbols inside real PS4/PS5 executables.
int guest_puts(const char*) __asm__("YQ0navp+YIc#A#A");             // puts
int guest_printf(const char*, ...) __asm__("hcuQgD53UxM#A#A");      // printf
int guest_usleep(unsigned) __asm__("1jfXLRVzisc#B#B");             // sceKernelUsleep
int guest_unknown(int) __asm__("AAAAAAAAAAA#B#B");                 // not implemented -> stub

void _start(void* params, void (*exit_handler)(void)) {
    (void)params;
    (void)exit_handler;
    guest_puts("Guest started");
    guest_usleep(1000);
    guest_unknown(7);
    guest_printf("Hello from the guest! %d 0x%x %s\n", 42, 42, "ps5");
}
