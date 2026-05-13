import styles from "./CodeEditorSkeleton.module.css";

export function CodeEditorSkeleton() {
  return (
    <div className={styles.skeleton} aria-label="Loading code editor..." role="status">
      <div className={`${styles.skeletonLine} ${styles["skeletonLine--medium"]}`} />
      <div className={`${styles.skeletonLine} ${styles["skeletonLine--long"]}`} />
      <div className={`${styles.skeletonLine} ${styles["skeletonLine--full"]}`} />
      <div className={`${styles.skeletonLine} ${styles["skeletonLine--medium"]}`} />
      <div className={`${styles.skeletonLine} ${styles["skeletonLine--short"]}`} />
      <div className={`${styles.skeletonLine} ${styles["skeletonLine--long"]}`} />
      <div className={`${styles.skeletonLine} ${styles["skeletonLine--full"]}`} />
      <div className={`${styles.skeletonLine} ${styles["skeletonLine--medium"]}`} />
      <div className={`${styles.skeletonLine} ${styles["skeletonLine--short"]}`} />
      <span className="sr-only">Loading Monaco editor...</span>
    </div>
  );
}
