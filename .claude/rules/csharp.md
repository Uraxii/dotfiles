# C# Rules

- Nullable reference types: `<Nullable>enable</Nullable>`. Handle nulls explicitly.
- `using` / `await using` for all `IDisposable`. No manual `.Dispose()`.
- No `dynamic`. Ever.
- `sealed` by default on classes. Unseal only when inheritance designed.
- `readonly struct` for small value types. Avoid mutable structs.
- `async/await` for IO. No `.Result` / `.Wait()` / `.GetAwaiter().GetResult()`.
- Pattern matching over type casting (`is Type t` over `as` + null check).
- `record` / `record struct` for immutable data. No manual Equals/GetHashCode.
- `span<T>` / `Memory<T>` over array slicing for perf-critical paths.
- No `public` fields. Properties only (even on internal types).
- `ConfigureAwait(false)` in library code. Omit in app/UI code.
- String interpolation over `String.Format`. `StringComparison.Ordinal` for non-user strings.
- `IAsyncEnumerable` for streaming data. No buffering entire collections.
- `ArgumentException` / `ArgumentNullException` at public API boundaries.
- Collection expressions (`[1, 2, 3]`) over `new List<int>{...}` (C# 12+).
