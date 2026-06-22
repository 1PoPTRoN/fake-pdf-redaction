type Props = { text: string };

/**
 * Marquee strip — repeats the message twice so the loop is seamless.
 */
export function Marquee({ text }: Props) {
  const block = (
    <span className="inline-flex items-center gap-6 px-6 font-display uppercase tracking-wider text-base sm:text-lg whitespace-nowrap">
      {text.split(" * ").map((chunk, i) => (
        <span key={i} className="inline-flex items-center gap-6">
          <span>{chunk}</span>
          <span aria-hidden>★</span>
        </span>
      ))}
    </span>
  );

  return (
    <div className="w-full overflow-hidden border-y-3 border-ink bg-sun">
      <div className="flex brutal-marquee whitespace-nowrap py-3">
        {block}
        {block}
      </div>
    </div>
  );
}