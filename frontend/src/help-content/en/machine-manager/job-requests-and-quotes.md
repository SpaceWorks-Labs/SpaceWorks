---
title: Run the job queue
summary: Accept member job requests, send quotes, run jobs singly or in batches, and finish or fail them.
order: 20
keywords: job requests, queue, quote, accept job, start job, batch, complete, failed, pickup, 3d printing, service queue
modules: machine_service
---
## Choose how a type takes jobs

1. Open the machine type, then **Settings**, then **Job requests**.
2. Tick **Members can send job requests for this type**.
3. Choose when a quote is needed: when the job has a price, always, above an amount, or never.
4. Choose when members pay: when the job is done, or before it joins the queue.
5. Set the open jobs per member and the longest job, then press **Save job settings**.

## Work the queue

1. Open **Service queue** on the type.
2. For each request: **Accept job**, **Send quote**, **Ask for changes** or **Reject job**.
3. **Assign to a machine** and **Start job**. **Mark urgent** moves it up.
4. When done, press **Complete job**, with the actual minutes and where to collect it. If it went wrong, **Mark job failed** and say what happened and whose fault it was.

![Screenshot: the Service queue with job actions](screenshot:mm-service-queue)

If a run fails through the space's or the machine's fault, the member pays nothing and the job goes back to the front of the queue.

## Batches

Where batch start is on, open **Queue board**, tick two or more jobs and press **Start as batch**, then **Start batch**. Finish with **Complete batch**.

## Printing

3D printing is a machine type like any other. **Log usage** records filament and minutes used outside a job.

> **Who can do this:** Machine Managers for their types, and the Space Manager. Finished jobs are handed over at [Job pickups](help:handover/job-handover).
