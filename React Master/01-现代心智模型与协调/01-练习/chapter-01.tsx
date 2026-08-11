// 1. 先预测点击“末项置顶”后会发生什么；分别解释不更新和输入草稿串号的根因。
// 2. 修复排序和 key。
// 3. 产品新增“切换任务时，未保存草稿必须重置”为明确需求。给两种方案：提升 draft 状态；或用 key 有意重置。说明各自适用约束。
// 4. 添加测试：在第二行输入“自定义”，置顶后草稿仍跟随任务 `b`，而不是留在第二个位置。

import { useState } from "react";

type Task = {
  id: string;
  title: string;
};

const tasks: Task[] = [
  { id: "a", title: "读讲义" },
  { id: "b", title: "自定义" },
  { id: "c", title: "写复盘" },
];

export function TaskBoard() {
  const [task, setTask] = useState({
    id: "a",
    title: "讲义",
  });

  return (
    <>
      {task.id}
      <Editor task={task} />
      <button onClick={() => setTask({ id: "b", title: "更换" })}>
        点击设置
      </button>
    </>
  );
}
function Editor({ task }) {
  const [darft, setDraft] = useState(task.title);
  console.log("看看这里的数据", darft);
  return <input value={darft} onChange={(e) => setDraft(e.target.value)} />;
}
// export function TaskBoard() {
//   const [selectedId, setSelectedId] = useState("a")

//   const selectedTask = tasks.find((task) => task.id === selectedId)!

//   return (
//     <>
//       <div>
//         {tasks.map((task) => (
//           <button key={task.id} onClick={() => setSelectedId(task.id)}>
//             编辑 {task.id}
//           </button>
//         ))}
//       </div>

//       <EditableRow key={selectedTask.id} task={selectedTask} />
//     </>
//   )
// }

// function EditableRow({ task }: { task: Task }) {
//   const [draft, setDraft] = useState(task.title)

//   return <input value={draft} onChange={(e) => setDraft(e.target.value)} />
// }
