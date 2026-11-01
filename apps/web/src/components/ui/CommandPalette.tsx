import React from "react";
import { createPortal } from "react-dom";
import { useNavigate } from "react-router-dom";
import { IconArrowRight, IconCornerDownLeft, IconSearch } from "@tabler/icons-react";

export interface Command {
  id: string;
  label: string;
  group: string;
  icon?: React.ReactNode;
  /** Route to open, or an action to run. */
  to?: string;
  run?: () => void;
  keywords?: string;
}

/**
 * Keyboard command palette (Ctrl/Cmd + K) in a Tabler modal: type to filter,
 * arrows to move, Enter to run, Escape to close.
 */
export const CommandPalette: React.FC<{ commands: Command[]; open: boolean; onClose: () => void }> = ({ commands, open, onClose }) => {
  const navigate = useNavigate();
  const [query, setQuery] = React.useState("");
  const [active, setActive] = React.useState(0);
  const inputRef = React.useRef<HTMLInputElement>(null);
  const listId = React.useId();

  const results = React.useMemo(() => {
    const term = query.trim().toLowerCase();
    if (!term) return commands;
    return commands.filter((c) => `${c.label} ${c.group} ${c.keywords ?? ""}`.toLowerCase().includes(term));
  }, [commands, query]);

  React.useEffect(() => {
    if (!open) return;
    const opener = document.activeElement as HTMLElement | null;
    setQuery("");
    setActive(0);
    window.setTimeout(() => inputRef.current?.focus(), 0);
    return () => opener?.focus();
  }, [open]);

  React.useEffect(() => { setActive(0); }, [query]);

  if (!open) return null;

  const run = (command: Command | undefined) => {
    if (!command) return;
    onClose();
    if (command.to) navigate(command.to);
    command.run?.();
  };

  const onKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === "Escape") { event.preventDefault(); onClose(); }
    else if (event.key === "ArrowDown") { event.preventDefault(); setActive((i) => Math.min(i + 1, results.length - 1)); }
    else if (event.key === "ArrowUp") { event.preventDefault(); setActive((i) => Math.max(i - 1, 0)); }
    else if (event.key === "Enter") { event.preventDefault(); run(results[active]); }
  };

  let lastGroup = "";
  return createPortal(
    <>
      <div className="modal modal-blur show d-block ssi-palette" tabIndex={-1} onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
        <div className="modal-dialog modal-dialog-centered modal-lg" role="document">
          <div className="modal-content" role="dialog" aria-modal="true" aria-label="Command palette" onKeyDown={onKeyDown}>
            <div className="ssi-palette-search">
              <IconSearch size={20} aria-hidden="true" />
              <input
                ref={inputRef}
                type="text"
                className="form-control form-control-flush"
                placeholder="Search pages and actions…"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                role="combobox"
                aria-expanded="true"
                aria-controls={listId}
                aria-activedescendant={results[active] ? `${listId}-${results[active].id}` : undefined}
                aria-label="Search pages and actions"
              />
              <kbd className="ssi-kbd">Esc</kbd>
            </div>
            <ul id={listId} className="ssi-palette-list" role="listbox" aria-label="Results">
              {results.length === 0 && <li className="ssi-palette-empty">No matches for “{query}”.</li>}
              {results.map((command, index) => {
                const header = command.group !== lastGroup ? command.group : null;
                lastGroup = command.group;
                return (
                  <React.Fragment key={command.id}>
                    {header && <li className="ssi-palette-group" role="presentation">{header}</li>}
                    <li
                      id={`${listId}-${command.id}`}
                      role="option"
                      aria-selected={index === active}
                      className={["ssi-palette-item", index === active ? "active" : ""].filter(Boolean).join(" ")}
                      onMouseEnter={() => setActive(index)}
                      onMouseDown={(e) => { e.preventDefault(); run(command); }}
                    >
                      <span className="ssi-palette-icon" aria-hidden="true">{command.icon ?? <IconArrowRight size={18} />}</span>
                      <span className="flex-fill">{command.label}</span>
                      {index === active && <IconCornerDownLeft size={16} className="opacity-50" aria-hidden="true" />}
                    </li>
                  </React.Fragment>
                );
              })}
            </ul>
            <div className="ssi-palette-footer">
              <span><kbd className="ssi-kbd">↑</kbd><kbd className="ssi-kbd">↓</kbd> move</span>
              <span><kbd className="ssi-kbd">Enter</kbd> open</span>
              <span><kbd className="ssi-kbd">Ctrl</kbd><kbd className="ssi-kbd">K</kbd> toggle</span>
            </div>
          </div>
        </div>
      </div>
      <div className="modal-backdrop show" />
    </>,
    document.body,
  );
};
