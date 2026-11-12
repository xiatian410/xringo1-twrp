# Workspace maintenance

- Follow `ADAPTATION-GOALS.md`; OS4 haptics invocation is user-confirmed normal and is not the current investigation priority.
- Do not operate a phone or physical block device. Preserve the offline verification scope.
- Maintain production source changes as pinned device-tree patches. Final image builds require `installclean` and `make -j$(nproc)`.
- User authorized a public repository through their GitHub CLI account: `xiatian410/xringo1-twrp`.
- After each coherent batch of source/document/test changes, run the reviewed export and synchronize GitHub before reporting completion: `python3 scripts/sync_github.py --push --message "describe the actual change"`.
- Public synchronization includes maintained source/configuration, patches, scripts, tests and documentation. Exclude images, compiled files, original firmware blobs, private signing keys, raw device logs, local caches and credentials.
- Do not claim a push succeeded unless the remote branch points at the local commit. If synchronization fails, preserve the local work and report the exact failure.
- Use `docs/WORK-QUEUE.md` for current priorities; historical check-count entries are not the current work queue.
- Reuse existing evidence when its relevant sources, inputs and scope are unchanged. Repeat or expand verification only for a relevant change, new failure/evidence, or a named coverage gap that can affect a concrete implementation decision.
- Distinguish production fixes, new evidence and documentation maintenance in progress reports. Do not count another passing fixture or an unchanged image as a delivered functional fix.
