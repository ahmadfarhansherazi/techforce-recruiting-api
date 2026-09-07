// Shared debounce logic lives here rather than as a loose helper function.
export class Debouncer {
  private readonly delayMs: number
  private timeoutId: ReturnType<typeof setTimeout> | undefined

  constructor(delayMs: number) {
    this.delayMs = delayMs
  }

  run(callback: () => void): void {
    this.cancel()
    this.timeoutId = setTimeout(callback, this.delayMs)
  }

  cancel(): void {
    if (this.timeoutId !== undefined) {
      clearTimeout(this.timeoutId)
      this.timeoutId = undefined
    }
  }
}
