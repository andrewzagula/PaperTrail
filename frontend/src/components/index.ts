/* The component layer. Import from "@/components", not from the files
   underneath, so a move inside this folder stays inside this folder. */

export { AppShell, TopBar, Body } from "./shell/AppShell";

export {
  Button,
  Checkbox,
  Dropzone,
  Field,
  Input,
  Menu,
  Segmented,
  Select,
  Stepper,
  Tabs,
} from "./ui/controls";
export type {
  ButtonProps,
  ButtonVariant,
  MenuOption,
  SegmentedOption,
  TabItem,
} from "./ui/controls";

export {
  Cite,
  Kbd,
  Num,
  Provenance,
  Score,
  Spinner,
  Stage,
  StatusPill,
  Tag,
  Working,
  toneFor,
} from "./ui/display";
export type { StageState, StatusTone, TagTone } from "./ui/display";

export {
  CodeBlock,
  GapItem,
  Item,
  PageHeader,
  Panel,
  PanelBody,
  PanelHead,
  PlainList,
  Row,
  Section,
  SectionHead,
  SelectionBar,
  Split,
  Step,
  Toolbar,
  WarnPanel,
} from "./ui/layout";

export {
  Blank,
  Chip,
  ChipRow,
  Confirm,
  Empty,
  Fact,
  Facts,
  Notice,
  PageSkeleton,
  Skeleton,
} from "./ui/states";
