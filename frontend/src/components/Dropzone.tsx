import { useDropzone } from "react-dropzone";
import { FileIcon } from "./icons";

type Props = {
  onFile: (file: File) => void;
  disabled?: boolean;
};

export function Dropzone({ onFile, disabled }: Props) {
  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop: (accepted) => {
      const pdf = accepted.find(
        (f) =>
          f.type === "application/pdf" || f.name.toLowerCase().endsWith(".pdf"),
      );
      if (pdf) onFile(pdf);
    },
    accept: { "application/pdf": [".pdf"] },
    disabled,
    multiple: false,
  });

  return (
    <div
      {...getRootProps()}
      className={[
        "relative w-full cursor-pointer select-none",
        "border-5 border-ink",
        "bg-sky text-paper",
        "p-10 sm:p-16",
        "flex flex-col items-center justify-center text-center",
        "shadow-brutalLg",
        "transition-colors",
        isDragActive ? "bg-sun text-ink" : "",
        disabled ? "opacity-50 cursor-not-allowed" : "",
      ].join(" ")}
    >
      <input {...getInputProps()} />

      {/* Single file icon, big and centered */}
      <div className="flex items-end justify-center mb-6 sm:mb-8">
        <div className="w-20 h-24 sm:w-28 sm:h-32 border-5 border-ink bg-paper text-ink flex items-center justify-center transform -rotate-3">
          <FileIcon className="w-12 h-14 sm:w-16 sm:h-20" />
        </div>
      </div>

      <p
        className="font-display uppercase tracking-tight"
        style={{ fontSize: "clamp(1.5rem, 7vw, 3.75rem)" }}
      >
        {isDragActive ? "DROP IT!" : "DROP A PDF TO AUDIT"}
      </p>
      <p className="mt-4 font-body text-base sm:text-xl font-bold">
        one file · or click to choose
      </p>
    </div>
  );
}